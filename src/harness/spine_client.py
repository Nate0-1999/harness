"""Typed, non-functional mirror of the SPEC C.4 Spine API.

Every C.4 route has a client method, but P0 performs no HTTP requests. H2 is
responsible for implementing transport behavior and contract tests.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    features: MemoryFeatures | None
    rank: int | None


class ScoredMemoryCard(MemoryCard):
    """Inject/prepare card, where C.4 requires scoring details."""

    features: MemoryFeatures
    rank: int


class SimilarityMemoryCard(MemoryCard):
    """Dedup/search card, where C.4 requires scoring details to be null."""

    features: None
    rank: None


class MemoryUnit(ContractModel):
    """Shared C.4 projection of a C.2 memory_unit row, minus embedding."""

    memory_id: UUID
    principal_id: str
    label: str
    body: str
    kind: MemoryKind
    keywords: list[str]
    project_key: str | None
    thread_origin: str | None
    pin: bool
    status: MemoryStatus
    revision: int
    stats: JsonObject
    bias: float
    embedding_model: str
    created_at: datetime
    updated_at: datetime


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
    injected: list[ScoredMemoryCard]
    near_misses: list[ScoredMemoryCard]


class RemovedMemory(ContractModel):
    memory_id: UUID
    reason: RemovalReason


class InjectCommitRequest(ContractModel):
    injection_id: UUID
    removed: list[RemovedMemory]
    added_back: list[UUID]


class InjectCommitResponse(ContractModel):
    final_block: str
    wrong_removed: list[MemoryUnit]


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
    machine_id: str
    force: bool = False


class CreatedMemoryResponse(ContractModel):
    created: MemoryUnit


class SimilarMemoriesResponse(ContractModel):
    created: None
    similar: list[SimilarityMemoryCard]


type CreateMemoryResponse = CreatedMemoryResponse | SimilarMemoriesResponse


class DuplicateMemoryConflict(ContractModel):
    duplicate_of: SimilarityMemoryCard


class LabelConflictTarget(ContractModel):
    memory_id: UUID
    label: str


class LabelConflict(ContractModel):
    label_conflict: LabelConflictTarget


type CreateMemoryConflict = DuplicateMemoryConflict | LabelConflict


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
    machine_id: str


type PatchMemoryResponse = MemoryUnit


class RevisionConflict(ContractModel):
    conflict: MemoryUnit


type PatchMemoryConflict = RevisionConflict | LabelConflict


class ListMemoriesParams(ContractModel):
    project_key: str | None = None
    status: MemoryStatus | None = None
    q: str | None = None
    limit: int = Field(default=50, le=200)
    offset: int = 0


class PagedMemoryListResponse(ContractModel):
    items: list[MemoryUnit]
    total: int
    limit: int
    offset: int


class SearchRequest(ContractModel):
    principal_id: str
    query: str
    k: int = 10
    project_key: str | None = None


class SearchResponse(ContractModel):
    results: list[SimilarityMemoryCard]


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
        """Mirror POST /v1/memories."""
        raise NotImplementedError("POST /v1/memories belongs to H2")

    async def patch_memory(
        self, memory_id: UUID, request: PatchMemoryRequest
    ) -> PatchMemoryResponse:
        """Mirror PATCH /v1/memories/{id}."""
        raise NotImplementedError("PATCH /v1/memories/{id} belongs to H2")

    async def list_memories(self, params: ListMemoriesParams) -> PagedMemoryListResponse:
        """Mirror GET /v1/memories."""
        raise NotImplementedError("GET /v1/memories belongs to H2")

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Mirror POST /v1/search."""
        raise NotImplementedError("POST /v1/search belongs to H2")
