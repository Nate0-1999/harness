import inspect

import pytest

from harness.spine_client import (
    CreateMemoryRequest,
    InjectPrepareRequest,
    MemoryKind,
    SearchRequest,
    SpineClient,
)


def test_client_exposes_all_seven_c4_routes() -> None:
    methods = {
        name
        for name, value in inspect.getmembers(SpineClient, inspect.iscoroutinefunction)
        if not name.startswith("_")
    }

    assert methods == {
        "prepare_injection",
        "commit_injection",
        "submit_feedback",
        "create_memory",
        "patch_memory",
        "list_memories",
        "search",
    }


def test_prepare_request_mirrors_named_c4_fields() -> None:
    request = InjectPrepareRequest(
        thread_id="12345678-1234-5678-1234-567812345678",
        agent_id="agent-1",
        machine_id="machine-1",
        principal_id="principal-1",
        prompt="hello",
        model_context_tokens=200_000,
    )

    assert set(request.model_dump(exclude_none=True)) == {
        "thread_id",
        "agent_id",
        "machine_id",
        "principal_id",
        "prompt",
        "model_context_tokens",
    }


def test_create_request_does_not_invent_force_body_field() -> None:
    request = CreateMemoryRequest(
        principal_id="principal-1",
        label="Editor preference",
        body="The user prefers tabs.",
        kind=MemoryKind.PREFERENCE,
        editor="user",
    )

    assert "force" not in CreateMemoryRequest.model_fields
    assert "force" not in request.model_dump()


def test_search_default_is_literal_c4_value() -> None:
    request = SearchRequest(principal_id="principal-1", query="tabs")

    assert request.k == 10


@pytest.mark.asyncio
async def test_stub_has_no_transport_behavior() -> None:
    client = SpineClient("https://spine.invalid", "token")
    request = SearchRequest(principal_id="principal-1", query="tabs")

    with pytest.raises(NotImplementedError, match="belongs to H2"):
        await client.search(request)
