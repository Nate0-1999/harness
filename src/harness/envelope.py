"""Literal Pydantic representation of the SPEC C.7 WebSocket envelope."""

import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

# A ULID is 128 bits encoded as 26 Crockford Base32 characters. The leading
# character is limited to 0–7 so the 130-bit textual space cannot overflow.
_ULID_PATTERN = re.compile(r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$", re.IGNORECASE)


class MessageType(StrEnum):
    """The closed message-type set enabled for M1."""

    THREAD_CREATE = "thread.create"
    PROMPT_SUBMIT = "prompt.submit"
    GATE_OPEN = "gate.open"
    GATE_COMMIT = "gate.commit"
    RUN_DELTA = "run.delta"
    RUN_DONE = "run.done"
    MEMORY_PANEL_UPDATE = "memory.panel.update"
    ERROR = "error"


class Envelope(BaseModel):
    """A daemon↔browser message, relay-shaped from day one."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    v: Literal[1]
    id: str
    ts: datetime
    machine_id: str
    agent_id: str | None = None
    thread_id: str | None = None
    type: MessageType
    payload: Any

    @field_validator("v", mode="before")
    @classmethod
    def reject_boolean_version(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("v must be the numeric literal 1")
        return value

    @field_validator("id")
    @classmethod
    def require_ulid(cls, value: str) -> str:
        if not _ULID_PATTERN.fullmatch(value):
            raise ValueError("id must be a ULID")
        return value
