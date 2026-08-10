from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace
from typing import Protocol
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ask.models import QueryIntent, QueryPlan, RetrievalMode, RetrievedEvidence
from src.graph.models import GraphNode
from src.graph.repository import GraphRepository
from src.semantic.embeddings import EmbeddingProvider
from src.semantic.models import Document, EmbeddingSpace
from src.semantic.repository import SemanticRepository

MAX_TERMS = 8
MAX_TERM_LENGTH = 80
_TERM_PATTERN = re.compile(r"[\w./:#@+-]+", re.UNICODE)
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "did",
        "do",
        "does",
        "for",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "the",
        "to",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
    }
)


class QueryRetrievalStore(Protocol):
    async def search_documents(
        self, *, repository_id: UUID, repository_version_id: UUID, terms: Sequence[str], limit: int
    ) -> Sequence[Document]: ...

    async def active_embedding_space(self) -> EmbeddingSpace | None: ...

    async def search_nodes(
        self, *, repository_id: UUID, repository_version_id: UUID, terms: Sequence[str], limit: int
    ) -> Sequence[GraphNode]: ...


class PostgresQueryRetrievalStore:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def search_documents(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        terms: Sequence[str],
        limit: int,
    ) -> Sequence[Document]:
        statement = select(Document).where(
            Document.repository_id == repository_id,
            Document.repository_version_id == repository_version_id,
        )
        conditions = [
            or_(
                Document.title.ilike(f"%{term}%"),
                Document.source_key.ilike(f"%{term}%"),
                Document.content.ilike(f"%{term}%"),
            )
            for term in terms
        ]
        if conditions:
            statement = statement.where(or_(*conditions))
        result = await self.session.execute(
            statement.order_by(
                Document.source_type, Document.source_key, Document.chunk_index
            ).limit(limit)
        )
        return result.scalars().all()

    async def active_embedding_space(self) -> EmbeddingSpace | None:
        result = await self.session.execute(
            select(EmbeddingSpace)
            .where(EmbeddingSpace.is_active.is_(True))
            .order_by(EmbeddingSpace.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def search_nodes(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        terms: Sequence[str],
        limit: int,
    ) -> Sequence[GraphNode]:
        conditions = [
            or_(
                GraphNode.name.ilike(f"%{term}%"),
                GraphNode.canonical_key.ilike(f"%{term}%"),
                GraphNode.description.ilike(f"%{term}%"),
            )
            for term in terms
        ]
        statement = select(GraphNode).where(
            GraphNode.repository_id == repository_id,
            or_(
                GraphNode.repository_version_id == repository_version_id,
                GraphNode.repository_version_id.is_(None),
            ),
        )
        if conditions:
            statement = statement.where(or_(*conditions))
        result = await self.session.execute(
            statement.order_by(GraphNode.confidence.desc(), GraphNode.canonical_key).limit(limit)
        )
        return result.scalars().all()


class AdaptiveQueryPlanner:
    def plan(self, question: str) -> QueryPlan:
        normalized = question.casefold()
        intent = _classify_intent(normalized)
        terms = tuple(
            dict.fromkeys(
                token[:MAX_TERM_LENGTH]
                for token in _TERM_PATTERN.findall(normalized)
                if len(token) > 1 and token not in _STOP_WORDS
            )
        )[:MAX_TERMS]
        modes = {
            QueryIntent.ARCHITECTURE: (
                RetrievalMode.GRAPH,
                RetrievalMode.VECTOR,
                RetrievalMode.METADATA,
            ),
            QueryIntent.HISTORY: (
                RetrievalMode.METADATA,
                RetrievalMode.GRAPH,
                RetrievalMode.VECTOR,
            ),
            QueryIntent.DECISION: (
                RetrievalMode.GRAPH,
                RetrievalMode.METADATA,
                RetrievalMode.VECTOR,
            ),
            QueryIntent.CONTRIBUTOR: (
                RetrievalMode.GRAPH,
                RetrievalMode.METADATA,
            ),
            QueryIntent.CODE: (
                RetrievalMode.METADATA,
                RetrievalMode.VECTOR,
                RetrievalMode.GRAPH,
            ),
            QueryIntent.GENERAL: (
                RetrievalMode.VECTOR,
                RetrievalMode.METADATA,
                RetrievalMode.GRAPH,
            ),
        }[intent]
        return QueryPlan(intent=intent, modes=modes, terms=terms)


class EntityResolver:
    """Resolve question terms to bounded graph entities with explainable lexical signals."""

    def resolve(
        self, question: str, candidates: Sequence[GraphNode], *, limit: int = 4
    ) -> tuple[GraphNode, ...]:
        normalized = question.casefold()

        def score(node: GraphNode) -> tuple[int, float, str]:
            name = node.name.casefold()
            canonical_key = node.canonical_key.casefold()
            exact_name = int(name == normalized.strip())
            phrase_match = int(name in normalized or canonical_key in normalized)
            token_overlap = sum(
                token in name or token in canonical_key
                for token in _TERM_PATTERN.findall(normalized)
                if token not in _STOP_WORDS
            )
            return (
                exact_name * 100 + phrase_match * 20 + token_overlap,
                node.confidence,
                node.id.hex,
            )

        return tuple(sorted(candidates, key=score, reverse=True)[:limit])


class HybridRetriever:
    def __init__(
        self,
        *,
        store: QueryRetrievalStore,
        semantic_repository: SemanticRepository,
        graph_repository: GraphRepository,
        embedding_provider: EmbeddingProvider,
        entity_resolver: EntityResolver | None = None,
    ) -> None:
        self.store = store
        self.semantic_repository = semantic_repository
        self.graph_repository = graph_repository
        self.embedding_provider = embedding_provider
        self.entity_resolver = entity_resolver or EntityResolver()

    async def retrieve(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        question: str,
        plan: QueryPlan,
        limit: int = 12,
    ) -> tuple[RetrievedEvidence, ...]:
        rankings = await self.retrieve_rankings(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            question=question,
            plan=plan,
            limit=limit,
        )
        return reciprocal_rank_fusion(rankings, terms=plan.terms, limit=limit)

    async def retrieve_rankings(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        question: str,
        plan: QueryPlan,
        limit: int = 12,
    ) -> dict[RetrievalMode, Sequence[RetrievedEvidence]]:
        rankings: dict[RetrievalMode, Sequence[RetrievedEvidence]] = {}
        for mode in plan.modes:
            if mode is RetrievalMode.METADATA:
                rankings[mode] = await self._metadata(
                    repository_id, repository_version_id, plan.terms, limit
                )
            elif mode is RetrievalMode.VECTOR:
                rankings[mode] = await self._vector(
                    repository_id, repository_version_id, question, limit
                )
            else:
                rankings[mode] = await self._graph(
                    repository_id, repository_version_id, plan.terms, limit
                )
        return rankings

    async def _metadata(
        self, repository_id: UUID, repository_version_id: UUID, terms: Sequence[str], limit: int
    ) -> tuple[RetrievedEvidence, ...]:
        documents = await self.store.search_documents(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            terms=terms,
            limit=limit,
        )
        return tuple(
            _document_evidence(document, RetrievalMode.METADATA, terms=terms)
            for document in documents
        )

    async def _vector(
        self, repository_id: UUID, repository_version_id: UUID, question: str, limit: int
    ) -> tuple[RetrievedEvidence, ...]:
        space = await self.store.active_embedding_space()
        if space is None or space.provider != self.embedding_provider.info.provider:
            return ()
        vectors = await self.embedding_provider.embed((question,))
        if not vectors:
            return ()
        results = await self.semantic_repository.nearest_neighbors(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            embedding_space_id=space.id,
            query_vector=vectors[0],
            limit=limit,
        )
        return tuple(
            replace(
                _document_evidence(
                    result.document,
                    RetrievalMode.VECTOR,
                    terms=_question_terms(question),
                ),
                score=max(0.0, 1.0 - result.cosine_distance),
            )
            for result in results
        )

    async def _graph(
        self, repository_id: UUID, repository_version_id: UUID, terms: Sequence[str], limit: int
    ) -> tuple[RetrievedEvidence, ...]:
        candidates = await self.store.search_nodes(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            terms=terms,
            limit=min(24, limit * 2),
        )
        roots = self.entity_resolver.resolve(" ".join(terms), candidates, limit=min(4, limit))
        evidence: list[RetrievedEvidence] = []
        seen: set[UUID] = set()
        for root in roots:
            snapshot = await self.graph_repository.neighbors(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                node_id=root.id,
                depth=1,
                limit=min(25, limit * 2),
                edge_limit=50,
                metric_limit=1,
                include_metrics=False,
            )
            for node in snapshot.nodes:
                if node.id in seen:
                    continue
                seen.add(node.id)
                stored_evidence, _ = await self.graph_repository.list_evidence(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    target_node_id=node.id,
                    limit=3,
                )
                excerpt = next((item.excerpt for item in stored_evidence if item.excerpt), None)
                source_url = next(
                    (item.source_url for item in stored_evidence if item.source_url), None
                )
                content = " — ".join(part for part in (node.description, excerpt) if part)
                if not content:
                    content = f"{node.entity_type.replace('_', ' ')}: {node.name}"
                evidence.append(
                    RetrievedEvidence(
                        id=f"node:{node.id}",
                        title=node.name,
                        content=content[:4000],
                        score=node.confidence,
                        modes=(RetrievalMode.GRAPH,),
                        source_type=node.entity_type,
                        source_url=source_url,
                        entity_id=node.id,
                        metadata={
                            "knowledge_kind": node.knowledge_kind,
                            "evaluation_key": f"node:{node.entity_type}:{node.name}",
                        },
                    )
                )
                if len(evidence) >= limit:
                    return tuple(evidence)
        return tuple(evidence)


def reciprocal_rank_fusion(
    rankings: dict[RetrievalMode, Sequence[RetrievedEvidence]],
    *,
    terms: Sequence[str],
    limit: int,
    rank_constant: int = 60,
) -> tuple[RetrievedEvidence, ...]:
    scores: dict[str, float] = {}
    items: dict[str, RetrievedEvidence] = {}
    modes: dict[str, set[RetrievalMode]] = {}
    normalized_terms = tuple(term.casefold() for term in terms)
    for mode, ranking in rankings.items():
        for rank, item in enumerate(ranking, start=1):
            items.setdefault(item.id, item)
            modes.setdefault(item.id, set()).add(mode)
            haystack = f"{item.title} {item.content}".casefold()
            overlap = sum(term in haystack for term in normalized_terms)
            scores[item.id] = scores.get(item.id, 0.0) + 1 / (rank_constant + rank)
            scores[item.id] += min(0.02, overlap * 0.004)
    ordered = sorted(items.values(), key=lambda item: (-scores[item.id], item.id))[:limit]
    return tuple(
        replace(
            item,
            score=round(scores[item.id], 6),
            modes=tuple(mode for mode in RetrievalMode if mode in modes[item.id]),
        )
        for item in ordered
    )


def _document_evidence(
    document: Document, mode: RetrievalMode, *, terms: Sequence[str]
) -> RetrievedEvidence:
    return RetrievedEvidence(
        id=f"doc:{document.id}",
        title=document.title or document.source_key,
        content=_relevant_excerpt(document.content, terms),
        score=0.0,
        modes=(mode,),
        source_type=document.source_type,
        source_url=document.source_url,
        entity_id=document.source_node_id,
        metadata={
            "evaluation_key": _document_evaluation_key(document),
            "source_key": document.source_key,
            "start_line": document.start_line,
            "end_line": document.end_line,
        },
    )


def _classify_intent(question: str) -> QueryIntent:
    intent_terms = (
        (QueryIntent.CONTRIBUTOR, ("author", "contributor", "maintain", "review", "who")),
        (QueryIntent.DECISION, ("decision", "rationale", "tradeoff", "why")),
        (QueryIntent.HISTORY, ("change", "history", "release", "timeline", "when")),
        (QueryIntent.ARCHITECTURE, ("architecture", "component", "depend", "subsystem")),
        (QueryIntent.CODE, ("class", "file", "function", "implement", "module", "symbol")),
    )
    for intent, keywords in intent_terms:
        if any(keyword in question for keyword in keywords):
            return intent
    return QueryIntent.GENERAL


def evidence_evaluation_key(evidence: RetrievedEvidence) -> str:
    value = evidence.metadata.get("evaluation_key")
    return value if isinstance(value, str) else evidence.id


def _document_evaluation_key(document: Document) -> str:
    title = document.title or ""
    return f"doc:{document.source_type}:{document.source_key}:{title}:{document.chunk_index}"


def _question_terms(question: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in _TERM_PATTERN.findall(question.casefold())
        if len(token) > 1 and token not in _STOP_WORDS
    )[:MAX_TERMS]


def _relevant_excerpt(content: str, terms: Sequence[str], *, limit: int = 900) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= limit:
        return normalized
    lowered = normalized.casefold()
    positions = [lowered.find(term.casefold()) for term in terms]
    matching_positions = [position for position in positions if position >= 0]
    center = min(matching_positions) if matching_positions else 0
    start = max(0, center - 140)
    end = min(len(normalized), start + limit)
    excerpt = normalized[start:end].strip()
    return f"{'… ' if start else ''}{excerpt}{' …' if end < len(normalized) else ''}"
