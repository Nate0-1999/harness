from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from harness.envelope import (
    Envelope,
    EnvelopeFactory,
    MessageType,
    StopReason,
    ThreadSnapshotResponsePayload,
)
from harness.run_loop import RunLoop
from harness.run_protocol import RunEmitter, TurnOutcome, UsageSnapshot

TEST_TIMEOUT = 1.0


def ulid(number: int) -> str:
    return f"{number:026d}"


@dataclass
class Ids:
    value: int = 100

    def next(self) -> str:
        self.value += 1
        return ulid(self.value)


@dataclass
class Sink:
    messages: list[Envelope] = field(default_factory=list)

    async def __call__(self, message: Envelope) -> None:
        self.messages.append(message)


@dataclass
class TurnControl:
    entered: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)
    cancellation_seen: asyncio.Event = field(default_factory=asyncio.Event)
    cleanup_release: asyncio.Event = field(default_factory=asyncio.Event)
    stop_reason: StopReason = StopReason.END_TURN
    usage: UsageSnapshot = UsageSnapshot()


class ControlledRunner:
    def __init__(self, controls: Mapping[str, TurnControl]) -> None:
        self.controls = controls
        self.calls: list[tuple[str, str, tuple[object, ...]]] = []
        self.emitters: dict[str, RunEmitter] = {}

    async def run(
        self,
        *,
        thread_id: str,
        prompt: str,
        message_history: Sequence[object],
        emit: RunEmitter,
    ) -> TurnOutcome:
        control = self.controls[prompt]
        self.calls.append((thread_id, prompt, tuple(message_history)))
        self.emitters[prompt] = emit
        control.entered.set()
        try:
            await control.release.wait()
        except asyncio.CancelledError:
            control.cancellation_seen.set()
            await asyncio.wait_for(control.cleanup_release.wait(), TEST_TIMEOUT)
            return TurnOutcome(
                stop_reason=StopReason.CANCELLED,
                message_history=(*message_history, f"{prompt}:cancelled-tool"),
                usage=control.usage,
            )
        return TurnOutcome(
            stop_reason=control.stop_reason,
            message_history=(*message_history, f"{prompt}:{control.stop_reason.value}"),
            usage=control.usage,
        )


class NeverStartsRunner:
    async def run(
        self,
        *,
        thread_id: str,
        prompt: str,
        message_history: Sequence[object],
        emit: RunEmitter,
    ) -> TurnOutcome:
        raise AssertionError("an immediately cancelled runner must not start")


class ImmediateHistoryRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def run(
        self,
        *,
        thread_id: str,
        prompt: str,
        message_history: Sequence[object],
        emit: RunEmitter,
    ) -> TurnOutcome:
        del thread_id, emit
        history = tuple(message_history)
        self.calls.append((prompt, history))
        return TurnOutcome(
            StopReason.END_TURN,
            (*history, f"{prompt}:complete"),
        )


class FinishBarrierLoop(RunLoop):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.finish_entered = asyncio.Event()
        self.release_finish = asyncio.Event()
        self._finish_count = 0

    async def _finish(
        self,
        thread_id: str,
        active: Any,
        outcome: TurnOutcome | None,
        stop_reason: StopReason,
    ) -> None:
        self._finish_count += 1
        if self._finish_count == 1:
            self.finish_entered.set()
            await self.release_finish.wait()
        await super()._finish(thread_id, active, outcome, stop_reason)


@dataclass
class BlockingSink:
    entered: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)
    calls: int = 0

    async def __call__(self, message: Envelope) -> None:
        del message
        self.calls += 1
        self.entered.set()
        await self.release.wait()


def factory(ids: Ids) -> EnvelopeFactory:
    return EnvelopeFactory(
        machine_id="machine-1",
        agent_id="agent-1",
        id_factory=ids.next,
        clock=lambda: datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
    )


def types(sink: Sink) -> list[MessageType | str]:
    return [message.type for message in sink.messages]


def payload(message: Envelope) -> dict[str, object]:
    value = message.payload
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    assert isinstance(value, dict)
    return value


@pytest.mark.asyncio
async def test_cancel_awaits_cleanup_preserves_partial_and_coalesces_duplicates() -> None:
    ids = Ids()
    control = TurnControl(usage=UsageSnapshot(1, 12, 3))
    runner = ControlledRunner({"hello": control})
    loop = RunLoop(runner, factory(ids))
    sink = Sink()
    await loop.attach(sink)

    run_id = await loop.submit(
        thread_id="thread-1",
        prompt_id=ulid(1),
        prompt="hello",
        sink=sink,
    )
    await _wait(control.entered)
    emit = runner.emitters["hello"]
    await emit.text("kept text")
    await emit.thinking("kept thought")
    await emit.event({"tool": "started"})
    await emit.usage(UsageSnapshot(1, 12, 3))
    await emit.open_gate({"memory_id": "memory-1"})

    first = asyncio.create_task(loop.cancel(thread_id=None, run_id=run_id, sink=sink))
    await _wait(control.cancellation_seen)
    duplicate = asyncio.create_task(loop.cancel(thread_id="thread-1", run_id=run_id, sink=sink))
    await asyncio.gather(first, duplicate)
    assert MessageType.RUN_DONE not in types(sink)
    assert MessageType.ERROR not in types(sink)

    control.cleanup_release.set()
    await _wait_for_done_count(sink, 1)

    message_types = types(sink)
    assert message_types.count(MessageType.RUN_DONE) == 1
    assert message_types.index(MessageType.GATE_DISMISS) < message_types.index(MessageType.RUN_DONE)
    done = next(message for message in sink.messages if message.type is MessageType.RUN_DONE)
    assert payload(done) == {
        "run_id": run_id,
        "stop_reason": StopReason.CANCELLED,
        "partial": True,
    }

    event_count = len(sink.messages)
    await emit.text("too late")
    await emit.usage(UsageSnapshot(2, 20, 4))
    assert len(sink.messages) == event_count

    await loop.detach(sink)
    reconnected = Sink()
    await loop.attach(reconnected)
    await _wait_for_type_count(reconnected, MessageType.THREAD_SNAPSHOT, 1)
    assert types(reconnected) == [MessageType.THREAD_SNAPSHOT]
    snapshot = reconnected.messages[0].payload
    assert isinstance(snapshot, ThreadSnapshotResponsePayload)
    assert snapshot.active_run is None
    assistant = next(message for message in snapshot.messages if message["role"] == "assistant")
    assert assistant["content"] == "kept text"
    assert assistant["thinking"] == "kept thought"
    assert assistant["events"] == [{"tool": "started"}]
    assert assistant["partial"] is True
    await loop.close()


@pytest.mark.asyncio
async def test_cancel_before_run_task_first_step_still_confirms_once() -> None:
    ids = Ids()
    loop = RunLoop(NeverStartsRunner(), factory(ids))
    sink = Sink()
    await loop.attach(sink)

    run_id = await loop.submit(
        thread_id="thread-1",
        prompt_id=ulid(1),
        prompt="cancel immediately",
        sink=sink,
    )
    await loop.cancel(thread_id="thread-1", run_id=run_id, sink=sink)
    await loop.cancel(thread_id=None, run_id=run_id, sink=sink)
    await _wait_for_done_count(sink, 1)

    assert types(sink).count(MessageType.RUN_DONE) == 1
    assert MessageType.ERROR not in types(sink)
    done = next(message for message in sink.messages if message.type is MessageType.RUN_DONE)
    assert payload(done) == {
        "run_id": run_id,
        "stop_reason": StopReason.CANCELLED,
        "partial": True,
    }
    await loop.close()


@pytest.mark.asyncio
async def test_cancel_racing_completed_model_preserves_outcome_for_queued_turn() -> None:
    ids = Ids()
    runner = ImmediateHistoryRunner()
    loop = FinishBarrierLoop(runner, factory(ids))
    sink = Sink()
    await loop.attach(sink)

    first_id = await loop.submit(
        thread_id="thread-1",
        prompt_id=ulid(1),
        prompt="first",
        sink=sink,
    )
    await _wait(loop.finish_entered)
    second_id = await loop.submit(
        thread_id="thread-1",
        prompt_id=ulid(2),
        prompt="second",
        sink=sink,
    )

    await loop.cancel(thread_id=None, run_id=first_id, sink=sink)
    loop.release_finish.set()
    await _wait_for_done_count(sink, 2)

    assert runner.calls == [
        ("first", ()),
        ("second", ("first:complete",)),
    ]
    indexed = [(message.type, payload(message).get("run_id")) for message in sink.messages]
    assert indexed.index((MessageType.RUN_DONE, first_id)) < indexed.index(
        (MessageType.RUN_STARTED, second_id)
    )
    first_done = next(
        message
        for message in sink.messages
        if message.type is MessageType.RUN_DONE and payload(message)["run_id"] == first_id
    )
    assert payload(first_done)["stop_reason"] is StopReason.CANCELLED
    await loop.close()


@pytest.mark.asyncio
async def test_close_does_not_interrupt_cancellation_cleanup_a_second_time() -> None:
    ids = Ids()
    control = TurnControl()
    loop = RunLoop(ControlledRunner({"hello": control}), factory(ids))
    sink = Sink()
    await loop.attach(sink)
    run_id = await loop.submit(
        thread_id="thread-1",
        prompt_id=ulid(1),
        prompt="hello",
        sink=sink,
    )
    await _wait(control.entered)
    await loop.cancel(thread_id="thread-1", run_id=run_id, sink=sink)
    await _wait(control.cancellation_seen)

    closing = asyncio.create_task(loop.close())
    await asyncio.sleep(0)
    assert not closing.done()
    control.cleanup_release.set()
    await asyncio.wait_for(closing, TEST_TIMEOUT)

    assert loop._threads["thread-1"].message_history == ("hello:cancelled-tool",)


@pytest.mark.asyncio
async def test_slow_sink_is_bounded_without_one_task_per_delta() -> None:
    ids = Ids()
    control = TurnControl()
    runner = ControlledRunner({"hello": control})
    loop = RunLoop(runner, factory(ids))
    sink = BlockingSink()
    await loop.attach(sink)
    await loop.submit(
        thread_id="thread-1",
        prompt_id=ulid(1),
        prompt="hello",
        sink=sink,
    )
    await _wait(control.entered)
    await _wait(sink.entered)

    emitter = runner.emitters["hello"]
    for _ in range(1_000):
        await emitter.text("x")
    await asyncio.sleep(0)

    delivery_tasks = [
        task
        for task in asyncio.all_tasks()
        if task.get_name() == "harness-envelope-delivery" and not task.done()
    ]
    assert len(delivery_tasks) <= 1
    assert sink.calls == 1
    assert loop._subscriptions == []

    control.release.set()
    for _ in range(100):
        if loop._threads["thread-1"].active is None:
            break
        await asyncio.sleep(0)
    assert loop._threads["thread-1"].active is None
    await loop.close()


@pytest.mark.asyncio
async def test_fifo_runs_once_and_survives_error_and_budget_terminals() -> None:
    ids = Ids()
    first = TurnControl(stop_reason=StopReason.ERROR)
    second = TurnControl(
        stop_reason=StopReason.BUDGET_EXCEEDED,
        usage=UsageSnapshot(2, 30, 8),
    )
    third = TurnControl(stop_reason=StopReason.END_TURN)
    runner = ControlledRunner({"first": first, "second": second, "third": third})
    loop = RunLoop(runner, factory(ids))
    sink = Sink()
    await loop.attach(sink)

    first_id = await loop.submit(thread_id="thread-1", prompt_id=ulid(1), prompt="first", sink=sink)
    await _wait(first.entered)
    second_id = await loop.submit(
        thread_id="thread-1", prompt_id=ulid(2), prompt="second", sink=sink
    )
    third_id = await loop.submit(thread_id="thread-1", prompt_id=ulid(3), prompt="third", sink=sink)
    await _wait_for_type_count(sink, MessageType.PROMPT_QUEUED, 2)
    assert [
        payload(message)["run_id"]
        for message in sink.messages
        if message.type is MessageType.PROMPT_QUEUED
    ] == [second_id, third_id]
    queued_snapshot_sink = Sink()
    await loop.request_snapshot("thread-1", queued_snapshot_sink)
    await _wait_for_type_count(queued_snapshot_sink, MessageType.THREAD_SNAPSHOT, 1)
    queued_snapshot = queued_snapshot_sink.messages[0].payload
    assert isinstance(queued_snapshot, ThreadSnapshotResponsePayload)
    assert queued_snapshot.active_run is not None
    assert [item.run_id for item in queued_snapshot.active_run.queued] == [
        second_id,
        third_id,
    ]
    queued_user_content = [
        message["content"] for message in queued_snapshot.messages if message["role"] == "user"
    ]
    assert queued_user_content == ["first", "second", "third"]

    first.release.set()
    await _wait(second.entered)
    second.release.set()
    await _wait(third.entered)
    third.release.set()
    await _wait_for_done_count(sink, 3)

    starts = [
        payload(message)["run_id"]
        for message in sink.messages
        if message.type is MessageType.RUN_STARTED
    ]
    assert starts == [first_id, second_id, third_id]
    done = [payload(message) for message in sink.messages if message.type is MessageType.RUN_DONE]
    assert [item["stop_reason"] for item in done] == [
        StopReason.ERROR,
        StopReason.BUDGET_EXCEEDED,
        StopReason.END_TURN,
    ]
    indexed = [(message.type, payload(message).get("run_id")) for message in sink.messages]
    assert indexed.index((MessageType.RUN_DONE, first_id)) < indexed.index(
        (MessageType.RUN_STARTED, second_id)
    )
    assert indexed.index((MessageType.RUN_DONE, second_id)) < indexed.index(
        (MessageType.RUN_STARTED, third_id)
    )
    assert [prompt for _, prompt, _ in runner.calls] == ["first", "second", "third"]
    assert runner.calls[0][2] == ()
    assert runner.calls[1][2] == ("first:error",)
    assert runner.calls[2][2] == (
        "first:error",
        "second:budget_exceeded",
    )

    snapshot_sink = Sink()
    await loop.request_snapshot("thread-1", snapshot_sink)
    await _wait_for_type_count(snapshot_sink, MessageType.THREAD_SNAPSHOT, 1)
    snapshot = snapshot_sink.messages[0].payload
    assert isinstance(snapshot, ThreadSnapshotResponsePayload)
    assert [message["role"] for message in snapshot.messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert snapshot.active_run is None
    await loop.close()


@dataclass
class SnapshotBarrierSink(Sink):
    snapshot_entered: asyncio.Event = field(default_factory=asyncio.Event)
    release_snapshot: asyncio.Event = field(default_factory=asyncio.Event)

    async def __call__(self, message: Envelope) -> None:
        self.messages.append(message)
        if message.type is MessageType.THREAD_SNAPSHOT:
            self.snapshot_entered.set()
            await self.release_snapshot.wait()


@pytest.mark.asyncio
async def test_attach_snapshot_is_atomic_before_new_live_delta() -> None:
    ids = Ids()
    control = TurnControl()
    runner = ControlledRunner({"hello": control})
    loop = RunLoop(runner, factory(ids))
    original = Sink()
    await loop.attach(original)
    await loop.submit(thread_id="thread-1", prompt_id=ulid(1), prompt="hello", sink=original)
    await _wait(control.entered)
    await loop.detach(original)

    reconnect = SnapshotBarrierSink()
    attach = asyncio.create_task(loop.attach(reconnect))
    await _wait(reconnect.snapshot_entered)
    await runner.emitters["hello"].text("after snapshot")
    await asyncio.sleep(0)
    assert types(reconnect) == [MessageType.THREAD_SNAPSHOT]

    reconnect.release_snapshot.set()
    await attach
    await _wait_for_type_count(reconnect, MessageType.RUN_DELTA, 1)
    assert types(reconnect) == [MessageType.THREAD_SNAPSHOT, MessageType.RUN_DELTA]
    assert MessageType.RUN_STARTED not in types(reconnect)
    control.release.set()
    await _wait_for_done_count(reconnect, 1)
    await loop.close()


@pytest.mark.asyncio
async def test_cancel_without_outer_thread_finds_run_after_selection_changes() -> None:
    ids = Ids()
    control = TurnControl()
    runner = ControlledRunner({"hello": control})
    loop = RunLoop(runner, factory(ids))
    sink = Sink()
    await loop.attach(sink)
    run_id = await loop.submit(thread_id="thread-1", prompt_id=ulid(1), prompt="hello", sink=sink)
    await _wait(control.entered)

    await loop.select("thread-2", sink)
    await loop.cancel(thread_id=None, run_id=run_id, sink=sink)
    await _wait(control.cancellation_seen)
    control.cleanup_release.set()
    await _wait_for_done_count(sink, 1)

    assert MessageType.ERROR not in types(sink)
    done = next(message for message in sink.messages if message.type is MessageType.RUN_DONE)
    assert done.thread_id == "thread-1"
    assert payload(done)["stop_reason"] is StopReason.CANCELLED
    await loop.close()


class RegressiveUsageRunner:
    async def run(
        self,
        *,
        thread_id: str,
        prompt: str,
        message_history: Sequence[object],
        emit: RunEmitter,
    ) -> TurnOutcome:
        await emit.usage(UsageSnapshot(2, 20, 4))
        await emit.usage(UsageSnapshot(1, 20, 4))
        raise AssertionError("regression must fail before this line")


@pytest.mark.asyncio
async def test_usage_regression_terminalizes_as_error_and_stale_cancel_is_scoped() -> None:
    ids = Ids()
    loop = RunLoop(RegressiveUsageRunner(), factory(ids))
    sink = Sink()
    await loop.attach(sink)
    run_id = await loop.submit(thread_id="thread-1", prompt_id=ulid(1), prompt="hello", sink=sink)
    await _wait_for_done_count(sink, 1)

    usage = [message for message in sink.messages if message.type is MessageType.RUN_USAGE]
    assert len(usage) == 1
    assert payload(usage[0]) == {
        "requests": 2,
        "input_tokens": 20,
        "output_tokens": 4,
        "run_id": run_id,
    }
    done = next(message for message in sink.messages if message.type is MessageType.RUN_DONE)
    assert payload(done)["stop_reason"] is StopReason.ERROR

    before = len(sink.messages)
    await loop.cancel(thread_id=None, run_id=run_id, sink=sink)
    await _wait_for_type_count(sink, MessageType.ERROR, 1)
    assert len(sink.messages) == before + 1
    assert sink.messages[-1].type is MessageType.ERROR
    assert payload(sink.messages[-1]) == {"code": "run_not_active", "run_id": run_id}
    await loop.close()


async def _wait_for_done_count(sink: Sink, expected: int) -> None:
    await _wait_for_type_count(sink, MessageType.RUN_DONE, expected)


async def _wait_for_type_count(
    sink: Sink,
    message_type: MessageType,
    expected: int,
) -> None:
    for _ in range(100):
        if types(sink).count(message_type) >= expected:
            return
        await asyncio.sleep(0)
    raise AssertionError(f"expected {expected} {message_type} messages")


async def _wait(event: asyncio.Event) -> None:
    await asyncio.wait_for(event.wait(), TEST_TIMEOUT)
