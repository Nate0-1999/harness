from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import pytest

from harness.envelope import GateCommitPayload, StopReason
from harness.memory_gate import MemoryGateTurnRunner
from harness.run_protocol import RunEmitter, TurnOutcome, UsageSnapshot
from harness.spine_client import (
    InjectCommitRequest,
    InjectCommitResponse,
    InjectPrepareRequest,
    InjectPrepareResponse,
    SpineTransportError,
)
from harness.tools_memory import MemoryToolContext

THREAD_ID = "22345678-1234-5678-1234-567812345678"
INJECTION_ID = UUID("32345678-1234-5678-1234-567812345678")
RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"


@dataclass
class RecordingDelegate:
    calls: list[tuple[str, str, tuple[object, ...], str | None]] = field(default_factory=list)

    async def run(
        self,
        *,
        thread_id: str,
        prompt: str,
        message_history: Sequence[object],
        emit: RunEmitter,
        system_instructions: str | None = None,
    ) -> TurnOutcome:
        del emit
        history = tuple(message_history)
        self.calls.append((thread_id, prompt, history, system_instructions))
        return TurnOutcome(StopReason.END_TURN, (*history, f"{prompt}:done"))


@dataclass
class RecordingEmitter:
    opened: asyncio.Event = field(default_factory=asyncio.Event)
    decision: asyncio.Future[GateCommitPayload] | None = None
    gate_value: Mapping[str, object] | None = None
    errors: list[Mapping[str, object]] = field(default_factory=list)
    events: list[str] = field(default_factory=list)

    async def text(self, value: str) -> None:
        del value

    async def thinking(self, value: str) -> None:
        del value

    async def event(self, value: Mapping[str, object]) -> None:
        del value

    async def usage(self, value: UsageSnapshot) -> None:
        del value

    async def open_gate(self, value: Mapping[str, object]) -> GateCommitPayload:
        self.gate_value = value
        self.events.append("gate.open")
        self.decision = asyncio.get_running_loop().create_future()
        self.opened.set()
        return await self.decision

    async def dismiss_gate(self) -> None:
        self.events.append("gate.dismiss")

    async def error(self, value: Mapping[str, object]) -> None:
        self.errors.append(value)
        self.events.append(f"error:{value['phase']}")


class RecordingSpine:
    def __init__(self, *, fail_prepare: bool = False, fail_commit: bool = False) -> None:
        self.fail_prepare = fail_prepare
        self.fail_commit = fail_commit
        self.prepare_requests: list[InjectPrepareRequest] = []
        self.commit_requests: list[InjectCommitRequest] = []

    async def prepare_injection(self, request: InjectPrepareRequest) -> InjectPrepareResponse:
        self.prepare_requests.append(request)
        if self.fail_prepare:
            raise SpineTransportError
        return InjectPrepareResponse(
            injection_id=INJECTION_ID,
            snapshot_ts=datetime(2026, 7, 21, 12, tzinfo=UTC),
            scorer_version="m1-v1",
            injected=[],
            near_misses=[],
        )

    async def commit_injection(self, request: InjectCommitRequest) -> InjectCommitResponse:
        self.commit_requests.append(request)
        if self.fail_commit:
            raise SpineTransportError
        return InjectCommitResponse(final_block="trusted memory block", wrong_removed=[])


def context_factory(spine: object):
    def create(thread_id: str) -> MemoryToolContext:
        assert thread_id == THREAD_ID
        return MemoryToolContext(
            spine=spine,  # type: ignore[arg-type]
            principal_id="principal-1",
            machine_id="machine-1",
            agent_id="agent-1",
            thread_id=UUID(thread_id),
            project_key="project-1",
            origin_path="/workspace/file.py",
        )

    return create


def decision(*, injection_id: UUID = INJECTION_ID) -> GateCommitPayload:
    return GateCommitPayload(
        run_id=RUN_ID,
        injection_id=injection_id,
        removed=[],
        added_back=[],
    )


@pytest.mark.asyncio
async def test_first_chat_blocks_commits_and_supplies_system_instructions_once() -> None:
    spine = RecordingSpine()
    delegate = RecordingDelegate()
    runner = MemoryGateTurnRunner(
        delegate,
        spine,
        context_factory(spine),
        model_context_tokens=1_000_000,
    )

    remember = await runner.run(
        thread_id=THREAD_ID,
        prompt="/remember keep this",
        message_history=(),
        emit=RecordingEmitter(),
    )
    assert remember.stop_reason is StopReason.END_TURN
    assert spine.prepare_requests == []

    emitted = RecordingEmitter()
    first = asyncio.create_task(
        runner.run(
            thread_id=THREAD_ID,
            prompt="ordinary chat",
            message_history=remember.message_history,
            emit=emitted,
        )
    )
    await asyncio.wait_for(emitted.opened.wait(), 1)
    assert [call[1] for call in delegate.calls] == ["/remember keep this"]
    assert len(spine.prepare_requests) == 1
    prepared = spine.prepare_requests[0]
    assert prepared.model_dump(mode="python") == {
        "thread_id": UUID(THREAD_ID),
        "agent_id": "agent-1",
        "machine_id": "machine-1",
        "principal_id": "principal-1",
        "project_key": "project-1",
        "agent_kind": None,
        "prompt": "ordinary chat",
        "model_context_tokens": 1_000_000,
    }
    assert emitted.decision is not None
    emitted.decision.set_result(decision())
    outcome = await asyncio.wait_for(first, 1)

    assert outcome.stop_reason is StopReason.END_TURN
    assert emitted.events == ["gate.open", "gate.dismiss"]
    assert spine.commit_requests == [
        InjectCommitRequest(injection_id=INJECTION_ID, removed=[], added_back=[])
    ]
    assert delegate.calls[-1][-1] == "trusted memory block"

    await runner.run(
        thread_id=THREAD_ID,
        prompt="second chat",
        message_history=outcome.message_history,
        emit=RecordingEmitter(),
    )
    assert len(spine.prepare_requests) == 1
    assert delegate.calls[-1][-1] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["prepare", "commit"])
async def test_spine_failure_is_visible_and_fails_open_without_instructions(phase: str) -> None:
    spine = RecordingSpine(
        fail_prepare=phase == "prepare",
        fail_commit=phase == "commit",
    )
    delegate = RecordingDelegate()
    runner = MemoryGateTurnRunner(
        delegate,
        spine,
        context_factory(spine),
        model_context_tokens=1_000_000,
    )
    emitted = RecordingEmitter()
    task = asyncio.create_task(
        runner.run(
            thread_id=THREAD_ID,
            prompt="hello",
            message_history=(),
            emit=emitted,
        )
    )
    if phase == "commit":
        await asyncio.wait_for(emitted.opened.wait(), 1)
        assert emitted.decision is not None
        emitted.decision.set_result(decision())
    await asyncio.wait_for(task, 1)

    assert emitted.errors == [
        {
            "code": "memory_unavailable",
            "phase": phase,
            "message": "Memory is unavailable; continuing without injected context.",
        }
    ]
    assert delegate.calls == [(THREAD_ID, "hello", (), None)]
    if phase == "prepare":
        assert emitted.events == ["error:prepare"]
    else:
        assert emitted.events == ["gate.open", "error:commit", "gate.dismiss"]


@pytest.mark.asyncio
async def test_cancelled_attempt_is_claimed_and_never_invokes_the_model() -> None:
    spine = RecordingSpine()
    delegate = RecordingDelegate()
    runner = MemoryGateTurnRunner(
        delegate,
        spine,
        context_factory(spine),
        model_context_tokens=1_000_000,
    )
    emitted = RecordingEmitter()
    first = asyncio.create_task(
        runner.run(
            thread_id=THREAD_ID,
            prompt="first",
            message_history=(),
            emit=emitted,
        )
    )
    await asyncio.wait_for(emitted.opened.wait(), 1)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert delegate.calls == []

    await runner.run(
        thread_id=THREAD_ID,
        prompt="next",
        message_history=(),
        emit=RecordingEmitter(),
    )
    assert len(spine.prepare_requests) == 1
    assert delegate.calls == [(THREAD_ID, "next", (), None)]


def test_gate_config_rejects_non_positive_or_boolean_context_windows() -> None:
    spine = RecordingSpine()
    for value in (0, -1, True):
        with pytest.raises(ValueError, match="positive integer"):
            MemoryGateTurnRunner(
                RecordingDelegate(),
                spine,
                context_factory(spine),
                model_context_tokens=value,
            )
