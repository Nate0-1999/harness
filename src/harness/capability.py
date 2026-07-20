"""Harness-owned capability contract, independent of any agent framework."""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

type CapabilityHandler = Callable[..., Awaitable[str]]
type CapabilityCallback = Callable[..., Any]


class CapabilityInstruction(BaseModel):
    """One static instruction contributed by a capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str


class CapabilityTool(BaseModel):
    """One contextual async tool exposed by a capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    handler: CapabilityHandler


class CapabilityLifecycleHook(BaseModel):
    """One named lifecycle callback; invocation semantics belong to its adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    handler: CapabilityCallback


class CapabilityHistoryTransform(BaseModel):
    """One named history transform; its payload contract is added at first use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    handler: CapabilityCallback


class CapabilityEventStreamTap(BaseModel):
    """One named event-stream tap; its event contract is added at first use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    handler: CapabilityCallback


class CapabilityDefinition(BaseModel):
    """The five ADR-013 axes of the Harness-owned capability protocol."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    instructions: tuple[CapabilityInstruction, ...] = ()
    tools: tuple[CapabilityTool, ...] = ()
    lifecycle_hooks: tuple[CapabilityLifecycleHook, ...] = ()
    history_transforms: tuple[CapabilityHistoryTransform, ...] = ()
    event_stream_taps: tuple[CapabilityEventStreamTap, ...] = ()


class HarnessCapability(Protocol):
    """Structural boundary implemented by every harness capability feature."""

    @property
    def definition(self) -> CapabilityDefinition: ...
