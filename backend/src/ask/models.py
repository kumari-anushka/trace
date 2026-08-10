from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class QueryIntent(StrEnum):
    ARCHITECTURE = "architecture"
    HISTORY = "history"
    DECISION = "decision"
    CONTRIBUTOR = "contributor"
    CODE = "code"
    GENERAL = "general"


class RetrievalMode(StrEnum):
    METADATA = "metadata"
    VECTOR = "vector"
    GRAPH = "graph"


@dataclass(frozen=True, slots=True)
class QueryPlan:
    intent: QueryIntent
    modes: tuple[RetrievalMode, ...]
    terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievedEvidence:
    id: str
    title: str
    content: str
    score: float
    modes: tuple[RetrievalMode, ...]
    source_type: str
    source_url: str | None = None
    entity_id: UUID | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AnswerClaim:
    text: str
    citation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnswerDraft:
    claims: tuple[AnswerClaim, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QueryResult:
    repository_id: UUID
    repository_version_id: UUID
    question: str
    answer: str
    claims: tuple[AnswerClaim, ...]
    citations: tuple[RetrievedEvidence, ...]
    limitations: tuple[str, ...]
    retrieval_modes: tuple[RetrievalMode, ...]
    grounded: bool
