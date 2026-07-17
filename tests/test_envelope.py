from datetime import datetime

import pytest
from pydantic import ValidationError

from harness.envelope import Envelope, MessageType


def valid_envelope() -> dict[str, object]:
    return {
        "v": 1,
        "id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "ts": "2026-07-17T12:00:00Z",
        "machine_id": "machine-1",
        "agent_id": "agent-1",
        "thread_id": "thread-1",
        "type": "prompt.submit",
        "payload": {"prompt": "hello"},
    }


def test_valid_c7_envelope() -> None:
    envelope = Envelope.model_validate(valid_envelope())

    assert envelope.v == 1
    assert envelope.type is MessageType.PROMPT_SUBMIT
    assert isinstance(envelope.ts, datetime)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("v", 2),
        ("id", "not-a-ulid"),
        ("id", "81ARZ3NDEKTSV4RRFFQ69G5FAV"),
        ("type", "relay.connect"),
    ],
)
def test_rejects_values_outside_c7(field: str, value: object) -> None:
    raw = valid_envelope()
    raw[field] = value

    with pytest.raises(ValidationError):
        Envelope.model_validate(raw)


def test_rejects_extra_fields() -> None:
    raw = valid_envelope()
    raw["localhost"] = True

    with pytest.raises(ValidationError):
        Envelope.model_validate(raw)


def test_optional_agent_and_thread_ids_may_be_absent() -> None:
    raw = valid_envelope()
    del raw["agent_id"]
    del raw["thread_id"]

    envelope = Envelope.model_validate(raw)

    assert envelope.agent_id is None
    assert envelope.thread_id is None
