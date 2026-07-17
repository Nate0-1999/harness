"""Typed, non-functional mirror of the SPEC C.4 Spine API.

Every C.4 route has a client method, but P0 performs no HTTP requests. H2 is
responsible for implementing transport behavior and contract tests.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

type JsonObject = dict[str, Any]


class ContractModel(BaseModel):
    """Closed JSON object for a body whose fields are specified in C.4."""

    model_config = ConfigDict(extra="forbid")


class MemoryKind(StrEnum):
    FACT = "fact"
    PREFERENCE = "preference"
    PROCEDURE = "procedure"
    PROJECT_NOTE = "project_note"
    PERSONA = "persona"
    PINNED = "pinned"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    QUARANTINED = "quarantined"
    TOMBSTONED = "tombstoned"


class RemovalReason(StrEnum):
    NOT_RELEVANT = "not_relevant"
    WRONG = "wrong"
    NEVER = "never"


class FeedbackSignal(StrEnum):
    MID_THREAD_REMOVED = "mid_thread_removed"
    CITED = "cited"


class MemoryFeatures(ContractModel):
    sem: float
    kw: float
    time: float
    proj: float
    freq: float
    hist: float


class MemoryCard(ContractModel):
    memory_id: UUID
    label: str
    body: str
    kind: MemoryKind
    pin: bool
    score: float
    features: MemoryFeatures
    rank: int


class InjectPrepareRequest(ContractModel):
    thread_id: UUID
    agent_id: str
    machine_id: str
    principal_id: str
    project_key: str | None = None
    agent_kind: str | None = None
    prompt: str
    model_context_tokens: int


class InjectPrepareResponse(ContractModel):
    injection_id: UUID
    snapshot_ts: datetime
    scorer_version: str
    injected: list[MemoryCard]
    near_misses: list[MemoryCard]


class RemovedMemory(ContractModel):
    memory_id: UUID
    reason: RemovalReason


class InjectCommitRequest(ContractModel):
    injection_id: UUID
    removed: list[RemovedMemory]
    added_back: list[UUID]


class InjectCommitResponse(ContractModel):
    final_block: str


class FeedbackRequest(ContractModel):
    injection_id: UUID
    memory_id: UUID
    signal: FeedbackSignal


class FeedbackResponse(ContractModel):
    ok: Literal[True]


class CreateMemoryRequest(ContractModel):
    principal_id: str
    label: str
    body: str
    kind: MemoryKind
    keywords: list[str] | None = None
    project_key: str | None = None
    thread_origin: str | None = None
    editor: str


class CreatedMemoryResponse(ContractModel):
    created: MemoryCard


class SimilarMemoriesResponse(ContractModel):
    created: None
    similar: list[MemoryCard]


type CreateMemoryResponse = CreatedMemoryResponse | SimilarMemoriesResponse


class DuplicateMemoryConflict(ContractModel):
    duplicate_of: MemoryCard


class PatchMemoryRequest(ContractModel):
    expected_revision: int
    body: str | None = None
    label: str | None = None
    keywords: list[str] | None = None
    kind: MemoryKind | None = None
    pin: bool | None = None
    status: MemoryStatus | None = None
    editor: str
    reason: str


# C.4 names these bodies but does not define their fields. They intentionally
# remain opaque until a contract owner specifies them; P0 must not invent law.
type PatchMemoryResponse = JsonObject
type PatchMemoryConflict = JsonObject


class ListMemoriesParams(ContractModel):
    project_key: str | None = None
    status: MemoryStatus | None = None
    q: str | None = None


type PagedMemoryListResponse = JsonObject


class SearchRequest(ContractModel):
    principal_id: str
    query: str
    k: int = 10
    project_key: str | None = None


class SearchResponse(ContractModel):
    results: list[MemoryCard]


class ProblemDetail(BaseModel):
    """RFC 7807 body; extension members are permitted by that standard."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    title: str | None = None
    status: int | None = None
    detail: str | None = None
    instance: str | None = None


class SpineClient:
    """C.4 method surface with no P0 transport or business behavior."""

    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    async def prepare_injection(self, request: InjectPrepareRequest) -> InjectPrepareResponse:
        """Mirror POST /v1/inject/prepare."""
        raise NotImplementedError("POST /v1/inject/prepare belongs to H2")

    async def commit_injection(self, request: InjectCommitRequest) -> InjectCommitResponse:
        """Mirror POST /v1/inject/commit."""
        raise NotImplementedError("POST /v1/inject/commit belongs to H2")

    async def submit_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        """Mirror POST /v1/feedback."""
        raise NotImplementedError("POST /v1/feedback belongs to H2")

    async def create_memory(self, request: CreateMemoryRequest) -> CreateMemoryResponse:
        """Mirror POST /v1/memories; C.4 does not place `force` in the body."""
        raise NotImplementedError("POST /v1/memories belongs to H2")

    async def patch_memory(
        self, memory_id: UUID, request: PatchMemoryRequest
    ) -> PatchMemoryResponse:
        """Mirror PATCH /v1/memories/{id}."""
        raise NotImplementedError("PATCH /v1/memories/{id} belongs to H2")

    async def list_memories(self, params: ListMemoriesParams) -> PagedMemoryListResponse:
        """Mirror GET /v1/memories; C.4 leaves the paged body undefined."""
        raise NotImplementedError("GET /v1/memories belongs to H2")

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Mirror POST /v1/search."""
        raise NotImplementedError("POST /v1/search belongs to H2")
