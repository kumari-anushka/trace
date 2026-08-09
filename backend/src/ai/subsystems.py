from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.graph.canonical import evidence_key
from src.graph.models import EntityType, EvidenceType, GraphEvidence, GraphNode, KnowledgeKind
from src.graph.repository import GraphEvidenceInput, GraphNodeInput, GraphRepository
from src.semantic.subsystems import SUBSYSTEM_DISCOVERY_VERSION

SUBSYSTEM_ENRICHMENT_PROMPT_VERSION = "subsystem-enrichment-v1"
SUBSYSTEM_ENRICHMENT_VERIFIER_VERSION = "subsystem-enrichment-verifier-v1"
MIN_CONFIRMED_CONFIDENCE = 0.8
MIN_CONFIRMED_CITATIONS = 2
MIN_CONFIRMED_COVERAGE = 0.5
MAX_SUBSYSTEM_NAME_CHARS = 80
MAX_SUBSYSTEM_SUMMARY_CHARS = 1_200


@dataclass(frozen=True, slots=True)
class SubsystemEvidenceInput:
    evidence_id: UUID
    source_node_id: UUID
    source_path: str
    excerpt: str
    signals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SubsystemEnrichmentInput:
    node_id: UUID
    canonical_key: str
    current_name: str
    current_description: str | None
    confidence: float
    member_paths: tuple[str, ...]
    signals: tuple[str, ...]
    evidence: tuple[SubsystemEvidenceInput, ...]
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class SubsystemEnrichmentProposal:
    name: str
    summary: str
    cited_evidence_ids: tuple[UUID, ...]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SubsystemEnrichmentProviderInfo:
    provider: str
    model: str
    model_revision: str | None = None


class SubsystemEnrichmentProvider(Protocol):
    @property
    def info(self) -> SubsystemEnrichmentProviderInfo: ...

    async def enrich(self, candidate: SubsystemEnrichmentInput) -> SubsystemEnrichmentProposal: ...


class SubsystemEnrichmentReader(Protocol):
    async def list_candidates(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> Sequence[SubsystemEnrichmentInput]: ...


@dataclass(frozen=True, slots=True)
class VerifiedSubsystemEnrichment:
    name: str
    summary: str
    status: str
    cited_evidence: tuple[SubsystemEvidenceInput, ...]
    limitations: tuple[str, ...]
    citation_coverage: float


@dataclass(frozen=True, slots=True)
class SubsystemEnrichmentSummary:
    provider_available: bool
    candidates: int
    enriched: int
    confirmed: int
    retained_as_candidates: int
    rejected: int
    model_evidence: int
    prompt_version: str = SUBSYSTEM_ENRICHMENT_PROMPT_VERSION
    verifier_version: str = SUBSYSTEM_ENRICHMENT_VERIFIER_VERSION


class SubsystemEnrichmentVerificationError(ValueError):
    """Raised when structured model output cannot be grounded in candidate evidence."""


class SubsystemEnrichmentProviderRejection(ValueError):
    """Raised when a provider returns no usable structured enrichment."""


class PostgresSubsystemEnrichmentReader:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def list_candidates(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> Sequence[SubsystemEnrichmentInput]:
        node_rows = await self.session.execute(
            select(GraphNode)
            .where(
                GraphNode.repository_id == repository_id,
                GraphNode.repository_version_id == repository_version_id,
                GraphNode.entity_type == EntityType.SUBSYSTEM,
                GraphNode.knowledge_kind == KnowledgeKind.INFERRED,
                GraphNode.provenance["algorithm"].as_string() == SUBSYSTEM_DISCOVERY_VERSION,
            )
            .order_by(GraphNode.canonical_key)
        )
        candidates = [
            node for node in node_rows.scalars().all() if node.details.get("status") == "candidate"
        ]
        if not candidates:
            return ()

        candidate_ids = [candidate.id for candidate in candidates]
        evidence_rows = await self.session.execute(
            select(GraphEvidence, GraphNode)
            .join(GraphNode, GraphNode.id == GraphEvidence.source_node_id)
            .where(
                GraphEvidence.repository_id == repository_id,
                GraphEvidence.repository_version_id == repository_version_id,
                GraphEvidence.target_node_id.in_(candidate_ids),
                GraphEvidence.evidence_type != EvidenceType.MODEL_INFERENCE,
            )
            .order_by(GraphEvidence.canonical_key)
        )
        evidence_by_candidate: dict[UUID, list[SubsystemEvidenceInput]] = {
            candidate.id: [] for candidate in candidates
        }
        for evidence, source_node in evidence_rows.all():
            if evidence.target_node_id is None:
                continue
            source_path = source_node.details.get("path")
            signals = evidence.details.get("signals")
            evidence_by_candidate[evidence.target_node_id].append(
                SubsystemEvidenceInput(
                    evidence_id=evidence.id,
                    source_node_id=source_node.id,
                    source_path=(source_path if isinstance(source_path, str) else source_node.name),
                    excerpt=evidence.excerpt or "",
                    signals=(
                        tuple(item for item in signals if isinstance(item, str))
                        if isinstance(signals, list)
                        else ()
                    ),
                )
            )

        return tuple(
            SubsystemEnrichmentInput(
                node_id=candidate.id,
                canonical_key=candidate.canonical_key,
                current_name=candidate.name,
                current_description=candidate.description,
                confidence=candidate.confidence,
                member_paths=_string_tuple(candidate.details.get("member_paths")),
                signals=_string_tuple(candidate.details.get("signals")),
                evidence=tuple(evidence_by_candidate[candidate.id]),
                metadata=dict(candidate.details),
            )
            for candidate in candidates
        )


class SubsystemEnrichmentVerifier:
    def verify(
        self,
        *,
        candidate: SubsystemEnrichmentInput,
        proposal: SubsystemEnrichmentProposal,
    ) -> VerifiedSubsystemEnrichment:
        name = " ".join(proposal.name.split())
        summary = " ".join(proposal.summary.split())
        if len(name) < 3 or len(name) > MAX_SUBSYSTEM_NAME_CHARS:
            raise SubsystemEnrichmentVerificationError(
                f"subsystem name must be between 3 and {MAX_SUBSYSTEM_NAME_CHARS} characters"
            )
        if len(summary) < 20 or len(summary) > MAX_SUBSYSTEM_SUMMARY_CHARS:
            raise SubsystemEnrichmentVerificationError(
                f"subsystem summary must be between 20 and {MAX_SUBSYSTEM_SUMMARY_CHARS} characters"
            )
        if not proposal.cited_evidence_ids:
            raise SubsystemEnrichmentVerificationError(
                "subsystem enrichment must cite candidate evidence"
            )

        evidence_by_id = {evidence.evidence_id: evidence for evidence in candidate.evidence}
        unknown_ids = set(proposal.cited_evidence_ids) - set(evidence_by_id)
        if unknown_ids:
            raise SubsystemEnrichmentVerificationError(
                "subsystem enrichment cites evidence outside the candidate"
            )
        cited_evidence = tuple(
            evidence_by_id[evidence_id]
            for evidence_id in dict.fromkeys(proposal.cited_evidence_ids)
        )
        cited_source_nodes = {evidence.source_node_id for evidence in cited_evidence}
        member_count = max(1, len(candidate.member_paths))
        coverage = min(1.0, len(cited_source_nodes) / member_count)
        confirmed = (
            candidate.confidence >= MIN_CONFIRMED_CONFIDENCE
            and len(cited_source_nodes) >= MIN_CONFIRMED_CITATIONS
            and coverage >= MIN_CONFIRMED_COVERAGE
        )
        return VerifiedSubsystemEnrichment(
            name=name,
            summary=summary,
            status="confirmed" if confirmed else "candidate",
            cited_evidence=cited_evidence,
            limitations=tuple(
                limitation.strip() for limitation in proposal.limitations if limitation.strip()
            ),
            citation_coverage=coverage,
        )


class SubsystemEnrichmentBuilder:
    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        reader: SubsystemEnrichmentReader,
        provider: SubsystemEnrichmentProvider | None,
        verifier: SubsystemEnrichmentVerifier | None = None,
    ) -> None:
        self.graph_repository = graph_repository
        self.reader = reader
        self.provider = provider
        self.verifier = verifier or SubsystemEnrichmentVerifier()

    async def build(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
    ) -> SubsystemEnrichmentSummary:
        if self.provider is None:
            return SubsystemEnrichmentSummary(
                provider_available=False,
                candidates=0,
                enriched=0,
                confirmed=0,
                retained_as_candidates=0,
                rejected=0,
                model_evidence=0,
            )

        candidates = await self.reader.list_candidates(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
        )
        enriched = 0
        confirmed = 0
        retained_as_candidates = 0
        rejected = 0
        model_evidence = 0
        provider_info = self.provider.info
        for candidate in candidates:
            try:
                proposal = await self.provider.enrich(candidate)
                verified = self.verifier.verify(candidate=candidate, proposal=proposal)
            except (
                SubsystemEnrichmentProviderRejection,
                SubsystemEnrichmentVerificationError,
            ):
                rejected += 1
                continue

            provenance: dict[str, object] = {
                "component": "subsystem_enrichment",
                "algorithm": SUBSYSTEM_DISCOVERY_VERSION,
                "provider": provider_info.provider,
                "model": provider_info.model,
                "model_revision": provider_info.model_revision,
                "prompt_version": SUBSYSTEM_ENRICHMENT_PROMPT_VERSION,
                "verifier_version": SUBSYSTEM_ENRICHMENT_VERIFIER_VERSION,
            }
            updated_node = await self.graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    entity_type=EntityType.SUBSYSTEM,
                    canonical_key=candidate.canonical_key,
                    name=verified.name,
                    description=verified.summary,
                    knowledge_kind=KnowledgeKind.INFERRED,
                    confidence=candidate.confidence,
                    provenance=provenance,
                    metadata={
                        **candidate.metadata,
                        "status": verified.status,
                        "cited_evidence_ids": [
                            str(evidence.evidence_id) for evidence in verified.cited_evidence
                        ],
                        "citation_coverage": verified.citation_coverage,
                        "limitations": list(verified.limitations),
                        "enrichment": {
                            "provider": provider_info.provider,
                            "model": provider_info.model,
                            "model_revision": provider_info.model_revision,
                            "prompt_version": SUBSYSTEM_ENRICHMENT_PROMPT_VERSION,
                            "verifier_version": SUBSYSTEM_ENRICHMENT_VERIFIER_VERSION,
                        },
                    },
                )
            )
            primary_evidence = verified.cited_evidence[0]
            await self.graph_repository.upsert_evidence(
                GraphEvidenceInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    canonical_key=evidence_key(
                        repository_id,
                        repository_version_id,
                        candidate.canonical_key,
                        provider_info.provider,
                        provider_info.model,
                        SUBSYSTEM_ENRICHMENT_PROMPT_VERSION,
                    ),
                    source_node_id=primary_evidence.source_node_id,
                    target_node_id=updated_node.id,
                    evidence_type=EvidenceType.MODEL_INFERENCE,
                    excerpt=verified.summary,
                    confidence=candidate.confidence,
                    provenance=provenance,
                    metadata={
                        "status": verified.status,
                        "cited_evidence_ids": [
                            str(evidence.evidence_id) for evidence in verified.cited_evidence
                        ],
                        "citation_coverage": verified.citation_coverage,
                        "limitations": list(verified.limitations),
                    },
                )
            )
            enriched += 1
            model_evidence += 1
            if verified.status == "confirmed":
                confirmed += 1
            else:
                retained_as_candidates += 1

        return SubsystemEnrichmentSummary(
            provider_available=True,
            candidates=len(candidates),
            enriched=enriched,
            confirmed=confirmed,
            retained_as_candidates=retained_as_candidates,
            rejected=rejected,
            model_evidence=model_evidence,
        )


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
