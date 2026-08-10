from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.graph.canonical import decision_key, evidence_key
from src.graph.models import (
    EntityType,
    EvidenceType,
    GraphEdge,
    GraphNode,
    KnowledgeKind,
    RelationshipType,
)
from src.graph.repository import (
    GraphEdgeInput,
    GraphEvidenceInput,
    GraphMetricInput,
    GraphNodeInput,
    GraphRepository,
)

HISTORICAL_INTELLIGENCE_VERSION = "historical-intelligence-v1"
CONTRIBUTOR_SCORE_WEIGHTS = {
    "authored_pull_requests": 0.30,
    "reviews": 0.20,
    "commits": 0.15,
    "subsystem_files": 0.20,
    "recency": 0.15,
}
BROAD_CHANGE_FILE_THRESHOLD = 10
MAX_DECISION_EVIDENCE = 50
_DECISION_LANGUAGE = re.compile(
    r"\b(adopt|architect|decid|deprecat|design|migrat|proposal|replace|rfc|switch)\w*\b",
    re.IGNORECASE,
)
_ALTERNATIVES_HEADING = re.compile(
    r"^#{1,6}\s+(?:alternatives?|options?)(?:\s+considered)?\s*$", re.IGNORECASE
)
_LIST_ITEM = re.compile(r"^\s*(?:[-*+] |\d+[.)]\s+)(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class HistoricalIntelligenceInput:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]


@dataclass(frozen=True, slots=True)
class DecisionCandidate:
    source: GraphNode
    context_nodes: tuple[GraphNode, ...]
    affected_files: tuple[GraphNode, ...]
    affected_subsystems: tuple[GraphNode, ...]
    status: str
    context: str
    selected_choice: str
    alternatives: tuple[str, ...]
    outcome: str
    confidence: float


@dataclass(frozen=True, slots=True)
class ContributorScore:
    person: GraphNode
    score: float
    authored_pull_requests: int
    reviews: int
    commits: int
    subsystem_files: int
    recency: float
    last_active_at: datetime | None
    active_subsystems: tuple[tuple[GraphNode, int], ...]
    normalized: dict[str, float]


@dataclass(frozen=True, slots=True)
class HistoricalIntelligenceFacts:
    decisions: tuple[DecisionCandidate, ...]
    contributors: tuple[ContributorScore, ...]


@dataclass(frozen=True, slots=True)
class HistoricalIntelligenceSummary:
    decisions: int
    confirmed_decisions: int
    insufficient_evidence_decisions: int
    decision_evidence: int
    contributor_scores: int
    stale_decisions: int
    algorithm_version: str = HISTORICAL_INTELLIGENCE_VERSION


class HistoricalIntelligenceReader(Protocol):
    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> HistoricalIntelligenceInput: ...


class HistoricalIntelligenceStore(Protocol):
    async def prune_decisions(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        retained_canonical_keys: Sequence[str],
    ) -> int: ...

    async def replace_metrics(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        algorithm_version: str,
        metrics: Sequence[GraphMetricInput],
    ) -> int: ...


class PostgresHistoricalIntelligenceStore:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> HistoricalIntelligenceInput:
        node_rows = await self.session.execute(
            select(GraphNode)
            .where(
                GraphNode.repository_id == repository_id,
                or_(
                    GraphNode.repository_version_id == repository_version_id,
                    GraphNode.repository_version_id.is_(None),
                ),
                GraphNode.entity_type.in_(
                    (
                        EntityType.PERSON,
                        EntityType.ISSUE,
                        EntityType.PULL_REQUEST,
                        EntityType.COMMIT,
                        EntityType.RELEASE,
                        EntityType.FILE,
                        EntityType.SUBSYSTEM,
                    )
                ),
            )
            .order_by(GraphNode.canonical_key)
        )
        nodes = tuple(node_rows.scalars().all())
        node_ids = tuple(node.id for node in nodes)
        if not node_ids:
            return HistoricalIntelligenceInput(nodes=(), edges=())
        edge_rows = await self.session.execute(
            select(GraphEdge)
            .where(
                GraphEdge.repository_id == repository_id,
                or_(
                    GraphEdge.repository_version_id == repository_version_id,
                    GraphEdge.repository_version_id.is_(None),
                ),
                GraphEdge.source_node_id.in_(node_ids),
                GraphEdge.target_node_id.in_(node_ids),
                GraphEdge.relationship_type.in_(
                    (
                        RelationshipType.AUTHORED,
                        RelationshipType.REVIEWED,
                        RelationshipType.MODIFIES,
                        RelationshipType.REFERENCES,
                        RelationshipType.RESOLVES,
                        RelationshipType.RELEASE_INCLUDES,
                        RelationshipType.PART_OF_SUBSYSTEM,
                    )
                ),
            )
            .order_by(GraphEdge.relationship_type, GraphEdge.id)
        )
        return HistoricalIntelligenceInput(
            nodes=nodes,
            edges=tuple(edge_rows.scalars().all()),
        )

    async def prune_decisions(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        retained_canonical_keys: Sequence[str],
    ) -> int:
        statement = delete(GraphNode).where(
            GraphNode.repository_id == repository_id,
            GraphNode.repository_version_id == repository_version_id,
            GraphNode.entity_type == EntityType.DECISION,
            GraphNode.provenance["algorithm"].as_string() == HISTORICAL_INTELLIGENCE_VERSION,
        )
        if retained_canonical_keys:
            statement = statement.where(GraphNode.canonical_key.not_in(retained_canonical_keys))
        result = await self.session.execute(statement)
        return int(getattr(result, "rowcount", 0) or 0)

    async def replace_metrics(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        algorithm_version: str,
        metrics: Sequence[GraphMetricInput],
    ) -> int:
        from src.graph.repository import PostgresGraphRepository

        return await PostgresGraphRepository(session=self.session).replace_metrics(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            algorithm_version=algorithm_version,
            metrics=metrics,
        )


class DeterministicHistoricalIntelligenceAnalyzer:
    def analyze(self, data: HistoricalIntelligenceInput) -> HistoricalIntelligenceFacts:
        nodes_by_id = {node.id: node for node in data.nodes}
        outgoing: dict[UUID, list[GraphEdge]] = defaultdict(list)
        for edge in data.edges:
            outgoing[edge.source_node_id].append(edge)
        decisions = self._decision_candidates(nodes_by_id, outgoing)
        contributors = self._contributor_scores(nodes_by_id, outgoing)
        return HistoricalIntelligenceFacts(decisions=decisions, contributors=contributors)

    def _decision_candidates(
        self,
        nodes: dict[UUID, GraphNode],
        outgoing: dict[UUID, list[GraphEdge]],
    ) -> tuple[DecisionCandidate, ...]:
        candidates: list[DecisionCandidate] = []
        for source in sorted(nodes.values(), key=lambda item: item.canonical_key):
            source_type = EntityType(source.entity_type)
            if source_type not in {
                EntityType.ISSUE,
                EntityType.PULL_REQUEST,
                EntityType.COMMIT,
                EntityType.RELEASE,
            }:
                continue
            direct_edges = outgoing[source.id]
            affected_files = _targets(
                direct_edges, nodes, RelationshipType.MODIFIES, EntityType.FILE
            )
            context_nodes = _targets(
                direct_edges,
                nodes,
                (RelationshipType.RESOLVES, RelationshipType.REFERENCES),
                (EntityType.ISSUE, EntityType.PULL_REQUEST),
            )
            if source_type is EntityType.RELEASE:
                included_commits = _targets(
                    direct_edges, nodes, RelationshipType.RELEASE_INCLUDES, EntityType.COMMIT
                )
                for commit in included_commits:
                    affected_files += _targets(
                        outgoing[commit.id], nodes, RelationshipType.MODIFIES, EntityType.FILE
                    )
            affected_files = _unique_nodes(affected_files)
            affected_subsystems = _subsystems_for_files(
                affected_files, nodes=nodes, outgoing=outgoing
            )

            merged = source_type is EntityType.PULL_REQUEST and _text_meta(source, "merged_at")
            broad_commit = (
                source_type is EntityType.COMMIT
                and len(affected_files) >= BROAD_CHANGE_FILE_THRESHOLD
            )
            linked_release = source_type is EntityType.RELEASE and bool(
                context_nodes or affected_files
            )
            decision_issue = source_type is EntityType.ISSUE and bool(
                _DECISION_LANGUAGE.search(f"{source.name}\n{source.description or ''}")
            )
            if not (merged or broad_commit or linked_release or decision_issue):
                continue

            has_implementation = bool(merged or broad_commit or linked_release)
            confirmed = bool(has_implementation and context_nodes and affected_files)
            status = "confirmed" if confirmed else "insufficient_evidence"
            confidence = min(
                0.95,
                (0.78 if confirmed else 0.42)
                + (0.05 if context_nodes else 0.0)
                + (0.05 if affected_files else 0.0)
                + (0.03 if affected_subsystems else 0.0),
            )
            candidates.append(
                DecisionCandidate(
                    source=source,
                    context_nodes=context_nodes,
                    affected_files=affected_files,
                    affected_subsystems=affected_subsystems,
                    status=status,
                    context=_decision_context(source, context_nodes),
                    selected_choice=_artifact_title(source),
                    alternatives=_extract_alternatives(source.description),
                    outcome=_decision_outcome(source, len(affected_files)),
                    confidence=confidence,
                )
            )
        return tuple(
            sorted(
                candidates,
                key=lambda item: (
                    item.status != "confirmed",
                    -item.confidence,
                    item.source.canonical_key,
                ),
            )
        )

    def _contributor_scores(
        self,
        nodes: dict[UUID, GraphNode],
        outgoing: dict[UUID, list[GraphEdge]],
    ) -> tuple[ContributorScore, ...]:
        people = [node for node in nodes.values() if node.entity_type == EntityType.PERSON]
        file_subsystems = {
            node.id: _targets(
                outgoing[node.id], nodes, RelationshipType.PART_OF_SUBSYSTEM, EntityType.SUBSYSTEM
            )
            for node in nodes.values()
            if node.entity_type == EntityType.FILE
        }
        raw: list[dict[str, object]] = []
        repository_activity_dates = [
            date for node in nodes.values() if (date := _activity_date(node)) is not None
        ]
        reference_date = max(repository_activity_dates, default=None)

        for person in people:
            authored = _targets(
                outgoing[person.id],
                nodes,
                RelationshipType.AUTHORED,
                (EntityType.PULL_REQUEST, EntityType.COMMIT),
            )
            reviewed = _targets(
                outgoing[person.id], nodes, RelationshipType.REVIEWED, EntityType.PULL_REQUEST
            )
            pull_requests = tuple(
                item for item in authored if item.entity_type == EntityType.PULL_REQUEST
            )
            commits = tuple(item for item in authored if item.entity_type == EntityType.COMMIT)
            activity_artifacts = _unique_nodes((*authored, *reviewed))
            changed_files = _unique_nodes(
                tuple(
                    file
                    for artifact in activity_artifacts
                    for file in _targets(
                        outgoing[artifact.id],
                        nodes,
                        RelationshipType.MODIFIES,
                        EntityType.FILE,
                    )
                )
            )
            subsystem_counts: Counter[UUID] = Counter()
            for file in changed_files:
                subsystem_counts.update(item.id for item in file_subsystems.get(file.id, ()))
            last_active_at = max(
                (date for item in activity_artifacts if (date := _activity_date(item)) is not None),
                default=None,
            )
            recency = _recency(last_active_at, reference_date)
            if not (pull_requests or reviewed or commits):
                continue
            raw.append(
                {
                    "person": person,
                    "authored_pull_requests": len(pull_requests),
                    "reviews": len(reviewed),
                    "commits": len(commits),
                    "subsystem_files": len(
                        {file.id for file in changed_files if file_subsystems.get(file.id)}
                    ),
                    "recency": recency,
                    "last_active_at": last_active_at,
                    "subsystem_counts": subsystem_counts,
                }
            )

        count_fields = (
            "authored_pull_requests",
            "reviews",
            "commits",
            "subsystem_files",
        )
        maxima = {
            field: max((cast(int, item[field]) for item in raw), default=0)
            for field in count_fields
        }
        results: list[ContributorScore] = []
        for item in raw:
            normalized = {
                field: _normalize_count(cast(int, item[field]), maxima[field])
                for field in count_fields
            }
            normalized["recency"] = cast(float, item["recency"])
            score = sum(
                normalized[field] * weight for field, weight in CONTRIBUTOR_SCORE_WEIGHTS.items()
            )
            subsystem_counts = cast(Counter[UUID], item["subsystem_counts"])
            active_subsystems = tuple(
                (nodes[node_id], count)
                for node_id, count in sorted(
                    subsystem_counts.items(),
                    key=lambda pair: (-pair[1], nodes[pair[0]].canonical_key),
                )
            )
            results.append(
                ContributorScore(
                    person=cast(GraphNode, item["person"]),
                    score=score,
                    authored_pull_requests=cast(int, item["authored_pull_requests"]),
                    reviews=cast(int, item["reviews"]),
                    commits=cast(int, item["commits"]),
                    subsystem_files=cast(int, item["subsystem_files"]),
                    recency=cast(float, item["recency"]),
                    last_active_at=cast(datetime | None, item["last_active_at"]),
                    active_subsystems=active_subsystems,
                    normalized=normalized,
                )
            )
        return tuple(sorted(results, key=lambda item: (-item.score, item.person.canonical_key)))


class HistoricalIntelligenceBuilder:
    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        reader: HistoricalIntelligenceReader,
        store: HistoricalIntelligenceStore,
        analyzer: DeterministicHistoricalIntelligenceAnalyzer | None = None,
    ) -> None:
        self.graph_repository = graph_repository
        self.reader = reader
        self.store = store
        self.analyzer = analyzer or DeterministicHistoricalIntelligenceAnalyzer()

    async def build(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> HistoricalIntelligenceSummary:
        data = await self.reader.read(
            repository_id=repository_id, repository_version_id=repository_version_id
        )
        facts = self.analyzer.analyze(data)
        stale_decisions = await self.store.prune_decisions(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            retained_canonical_keys=(),
        )
        provenance: dict[str, object] = {
            "component": "historical_intelligence",
            "algorithm": HISTORICAL_INTELLIGENCE_VERSION,
            "kind": "derived_from_non_model_evidence",
        }
        evidence_count = 0
        for candidate in facts.decisions:
            canonical_key = decision_key(
                repository_id, repository_version_id, candidate.source.canonical_key
            )
            decision = await self.graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    entity_type=EntityType.DECISION,
                    canonical_key=canonical_key,
                    name=candidate.selected_choice,
                    description=candidate.context,
                    knowledge_kind=KnowledgeKind.DERIVED,
                    confidence=candidate.confidence,
                    provenance=provenance,
                    metadata={
                        "status": candidate.status,
                        "context": candidate.context,
                        "selected_choice": candidate.selected_choice,
                        "alternatives": list(candidate.alternatives),
                        "outcome": candidate.outcome,
                        "source_node_id": str(candidate.source.id),
                        "source_url": candidate.source.details.get("html_url"),
                        "affected_files": [
                            {"id": str(file.id), "path": file.details.get("path", file.name)}
                            for file in candidate.affected_files
                        ],
                        "affected_subsystems": [
                            {"id": str(item.id), "name": item.name}
                            for item in candidate.affected_subsystems
                        ],
                        "evidence_chain": [
                            {"node_id": str(item.id), "role": "context"}
                            for item in candidate.context_nodes
                        ]
                        + [{"node_id": str(candidate.source.id), "role": "implementation"}],
                    },
                )
            )
            await self._edge(
                repository_id,
                repository_version_id,
                decision.id,
                candidate.source.id,
                RelationshipType.IMPLEMENTED_BY,
                candidate.confidence,
                provenance,
                {"status": candidate.status},
            )
            for context_node in candidate.context_nodes:
                await self._edge(
                    repository_id,
                    repository_version_id,
                    decision.id,
                    context_node.id,
                    RelationshipType.DERIVED_FROM,
                    candidate.confidence,
                    provenance,
                    {"role": "context"},
                )
            for affected in (*candidate.affected_files, *candidate.affected_subsystems):
                await self._edge(
                    repository_id,
                    repository_version_id,
                    decision.id,
                    affected.id,
                    RelationshipType.AFFECTS,
                    candidate.confidence,
                    provenance,
                    {"entity_type": affected.entity_type},
                )

            evidence_sources = _unique_nodes(
                (*candidate.context_nodes, candidate.source, *candidate.affected_files)
            )[:MAX_DECISION_EVIDENCE]
            for index, evidence_source in enumerate(evidence_sources):
                await self.graph_repository.upsert_evidence(
                    GraphEvidenceInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        canonical_key=evidence_key(
                            repository_id,
                            repository_version_id,
                            canonical_key,
                            evidence_source.canonical_key,
                            index,
                            HISTORICAL_INTELLIGENCE_VERSION,
                        ),
                        source_node_id=evidence_source.id,
                        target_node_id=decision.id,
                        evidence_type=(
                            EvidenceType.ARTIFACT
                            if evidence_source.entity_type != EntityType.FILE
                            else EvidenceType.PROVIDER_RELATION
                        ),
                        excerpt=(
                            evidence_source.description
                            or cast(str, evidence_source.details.get("path"))
                            or evidence_source.name
                        )[:1000],
                        source_url=cast(
                            str | None,
                            evidence_source.details.get("html_url")
                            or evidence_source.details.get("source_url"),
                        ),
                        confidence=candidate.confidence,
                        provenance=provenance,
                        metadata={"decision_status": candidate.status},
                    )
                )
                evidence_count += 1

        metrics = self._contributor_metrics(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            scores=facts.contributors,
        )
        await self.store.replace_metrics(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            algorithm_version=HISTORICAL_INTELLIGENCE_VERSION,
            metrics=metrics,
        )
        confirmed = sum(item.status == "confirmed" for item in facts.decisions)
        return HistoricalIntelligenceSummary(
            decisions=len(facts.decisions),
            confirmed_decisions=confirmed,
            insufficient_evidence_decisions=len(facts.decisions) - confirmed,
            decision_evidence=evidence_count,
            contributor_scores=len(facts.contributors),
            stale_decisions=stale_decisions,
        )

    async def _edge(
        self,
        repository_id: UUID,
        repository_version_id: UUID,
        source_node_id: UUID,
        target_node_id: UUID,
        relationship: RelationshipType,
        confidence: float,
        provenance: dict[str, object],
        metadata: dict[str, object],
    ) -> GraphEdge:
        return await self.graph_repository.upsert_edge(
            GraphEdgeInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                relationship_type=relationship,
                knowledge_kind=KnowledgeKind.DERIVED,
                confidence=confidence,
                provenance=provenance,
                metadata=metadata,
            )
        )

    def _contributor_metrics(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        scores: Sequence[ContributorScore],
    ) -> tuple[GraphMetricInput, ...]:
        metrics: list[GraphMetricInput] = []
        for rank, score in enumerate(scores, start=1):
            metadata: dict[str, object] = {
                "rank": rank,
                "weights": CONTRIBUTOR_SCORE_WEIGHTS,
                "normalized_components": score.normalized,
                "raw_components": {
                    "authored_pull_requests": score.authored_pull_requests,
                    "reviews": score.reviews,
                    "commits": score.commits,
                    "subsystem_files": score.subsystem_files,
                    "recency": score.recency,
                },
                "last_active_at": (
                    score.last_active_at.isoformat() if score.last_active_at else None
                ),
                "active_subsystems": [
                    {"node_id": str(node.id), "name": node.name, "file_count": count}
                    for node, count in score.active_subsystems
                ],
                "description": _contributor_description(score),
                "limitation": (
                    "Scores describe bounded repository activity and do not imply ownership."
                ),
            }
            values = {
                "contributor_activity_score": score.score,
                "contributor_authored_pull_requests": float(score.authored_pull_requests),
                "contributor_reviews": float(score.reviews),
                "contributor_commits": float(score.commits),
                "contributor_subsystem_files": float(score.subsystem_files),
                "contributor_recency": score.recency,
            }
            for metric_name, value in values.items():
                metrics.append(
                    GraphMetricInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        node_id=score.person.id,
                        metric_name=metric_name,
                        scope_key=score.person.canonical_key,
                        value=value,
                        algorithm_version=HISTORICAL_INTELLIGENCE_VERSION,
                        metadata=metadata,
                    )
                )
        return tuple(metrics)


def _targets(
    edges: Sequence[GraphEdge],
    nodes: dict[UUID, GraphNode],
    relationships: RelationshipType | tuple[RelationshipType, ...],
    entity_types: EntityType | tuple[EntityType, ...],
) -> tuple[GraphNode, ...]:
    relationship_values = (
        {item.value for item in relationships}
        if isinstance(relationships, tuple)
        else {relationships.value}
    )
    entity_values = (
        {item.value for item in entity_types}
        if isinstance(entity_types, tuple)
        else {entity_types.value}
    )
    return _unique_nodes(
        tuple(
            target
            for edge in edges
            if edge.relationship_type in relationship_values
            and (target := nodes.get(edge.target_node_id)) is not None
            and target.entity_type in entity_values
        )
    )


def _unique_nodes(nodes: Sequence[GraphNode]) -> tuple[GraphNode, ...]:
    return tuple({node.id: node for node in nodes}.values())


def _subsystems_for_files(
    files: Sequence[GraphNode],
    *,
    nodes: dict[UUID, GraphNode],
    outgoing: dict[UUID, list[GraphEdge]],
) -> tuple[GraphNode, ...]:
    return _unique_nodes(
        tuple(
            subsystem
            for file in files
            for subsystem in _targets(
                outgoing[file.id],
                nodes,
                RelationshipType.PART_OF_SUBSYSTEM,
                EntityType.SUBSYSTEM,
            )
        )
    )


def _artifact_title(node: GraphNode) -> str:
    return re.sub(r"^#\d+\s+", "", node.name).strip()


def _decision_context(source: GraphNode, context_nodes: Sequence[GraphNode]) -> str:
    if context_nodes:
        context = context_nodes[0]
        return (context.description or context.name).strip()
    return (source.description or source.name).strip()


def _decision_outcome(source: GraphNode, affected_file_count: int) -> str:
    if source.entity_type == EntityType.PULL_REQUEST:
        date = _text_meta(source, "merged_at")
        action = f"Merged{f' on {date[:10]}' if date else ''}"
    elif source.entity_type == EntityType.RELEASE:
        date = _text_meta(source, "published_at")
        action = f"Released{f' on {date[:10]}' if date else ''}"
    elif source.entity_type == EntityType.COMMIT:
        action = "Recorded in repository history"
    else:
        date = _text_meta(source, "closed_at")
        action = f"Issue closed{f' on {date[:10]}' if date else ''}"
    return f"{action}; {affected_file_count} affected file(s) are present in the snapshot graph."


def _extract_alternatives(body: str | None) -> tuple[str, ...]:
    if not body:
        return ()
    collecting = False
    alternatives: list[str] = []
    for line in body.splitlines():
        if _ALTERNATIVES_HEADING.match(line.strip()):
            collecting = True
            continue
        if collecting and line.lstrip().startswith("#"):
            break
        if collecting and (match := _LIST_ITEM.match(line)):
            alternatives.append(match.group(1)[:300])
            if len(alternatives) == 5:
                break
    return tuple(alternatives)


def _text_meta(node: GraphNode, key: str) -> str | None:
    value = node.details.get(key)
    return value if isinstance(value, str) and value else None


def _activity_date(node: GraphNode) -> datetime | None:
    for field in ("merged_at", "git_author_date", "published_at", "closed_at", "updated_at"):
        if value := _text_meta(node, field):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def _recency(last_active: datetime | None, reference: datetime | None) -> float:
    if last_active is None or reference is None:
        return 0.0
    days = max(0.0, (reference - last_active).total_seconds() / 86_400)
    return math.exp(-math.log(2) * days / 180.0)


def _normalize_count(value: int, maximum: int) -> float:
    return value / maximum if maximum else 0.0


def _contributor_description(score: ContributorScore) -> str:
    if score.active_subsystems:
        subsystem = score.active_subsystems[0][0].name
        return f"Repository evidence suggests strong recent activity around {subsystem}."
    return "Repository evidence suggests recent activity across the ingested history."
