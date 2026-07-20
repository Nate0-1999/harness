"""The single adapter from harness capabilities to pydantic-ai v2."""

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Capability
from pydantic_ai.tools import Tool

from harness.capability import CapabilityHandler, CapabilityTool, HarnessCapability
from harness.memory_capability import DEFAULT_MEMORY_FEATURE
from harness.spine_client import MemoryKind
from harness.tools_memory import MemoryToolContext


def _adapt_save(handler: CapabilityHandler) -> Tool[MemoryToolContext]:
    async def adapted_save(
        ctx: RunContext[MemoryToolContext],
        label: str,
        body: str,
        kind: MemoryKind,
        *,
        keywords: list[str] | None = None,
        project_scoped: bool,
        force: bool = False,
    ) -> str:
        return await handler(
            ctx.deps,
            label=label,
            body=body,
            kind=kind,
            keywords=keywords,
            project_scoped=project_scoped,
            force=force,
        )

    return Tool(adapted_save)


def _adapt_search(handler: CapabilityHandler) -> Tool[MemoryToolContext]:
    async def adapted_search(
        ctx: RunContext[MemoryToolContext],
        query: str,
        k: int = 5,
    ) -> str:
        return await handler(ctx.deps, query=query, k=k)

    return Tool(adapted_search)


def _adapt_edit(handler: CapabilityHandler) -> Tool[MemoryToolContext]:
    async def adapted_edit(
        ctx: RunContext[MemoryToolContext],
        label_or_id: str,
        new_body: str,
        reason: str,
    ) -> str:
        return await handler(
            ctx.deps,
            label_or_id=label_or_id,
            new_body=new_body,
            reason=reason,
        )

    return Tool(adapted_edit)


_CONTEXTUAL_ADAPTERS = {
    "save_memory": _adapt_save,
    "search_memory": _adapt_search,
    "edit_memory": _adapt_edit,
}


def _adapt_tool(spec: CapabilityTool) -> Tool[MemoryToolContext]:
    """Pair an owned tool spec with its explicit contextual schema."""
    try:
        adapter = _CONTEXTUAL_ADAPTERS[spec.name]
    except KeyError as exc:
        raise ValueError(f"unsupported memory tool: {spec.name}") from exc
    tool = adapter(spec.handler)
    tool.name = spec.name
    tool.description = spec.description
    return tool


class MemoryCapability(Capability[MemoryToolContext]):
    """Standard pydantic-ai capability backed by the harness memory feature."""

    def __init__(self, feature: HarnessCapability = DEFAULT_MEMORY_FEATURE) -> None:
        definition = feature.definition
        if definition.id != "memory":
            raise ValueError("MemoryCapability requires the memory feature")
        if tuple(tool.name for tool in definition.tools) != tuple(_CONTEXTUAL_ADAPTERS):
            raise ValueError("MemoryCapability requires exactly the three C.6 memory tools")
        if (
            definition.lifecycle_hooks
            or definition.history_transforms
            or definition.event_stream_taps
        ):
            raise ValueError(
                "MemoryCapability does not define lifecycle, history, or event behavior"
            )

        super().__init__(
            id=definition.id,
            defer_loading=False,
            instructions=[instruction.text for instruction in definition.instructions],
            tools=[_adapt_tool(tool) for tool in definition.tools],
        )
