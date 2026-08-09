from uuid import uuid4

import pytest

from src.ai.subsystems import (
    SubsystemEnrichmentBuilder,
    SubsystemEnrichmentInput,
    SubsystemEnrichmentProposal,
    SubsystemEnrichmentProviderInfo,
    SubsystemEnrichmentReader,
    SubsystemEnrichmentVerificationError,
    SubsystemEnrichmentVerifier,
    SubsystemEvidenceInput,
)
from src.graph.models import EntityType, EvidenceType, KnowledgeKind
from src.graph.repository import GraphNodeInput
from tests.graph.fakes import MemoryGraphRepository


def _candidate(*, confidence: float = 0.85) -> SubsystemEnrichmentInput:
    evidence = tuple(
        SubsystemEvidenceInput(
            evidence_id=uuid4(),
            source_node_id=uuid4(),
            source_path=path,
            excerpt=f"{path} grouped by directory and graph_community",
            signals=("directory", "graph_community", "embedding"),
        )
        for path in ("backend/api/routes.py", "backend/api/schemas.py")
    )
    return SubsystemEnrichmentInput(
        node_id=uuid4(),
        canonical_key="subsystem:api",
        current_name="Api candidate",
        current_description="Candidate cluster",
        confidence=confidence,
        member_paths=tuple(item.source_path for item in evidence),
        signals=("directory", "embedding", "graph_community"),
        evidence=evidence,
        metadata={"status": "candidate", "member_count": 2},
    )


def _proposal(candidate: SubsystemEnrichmentInput) -> SubsystemEnrichmentProposal:
    return SubsystemEnrichmentProposal(
        name="API Layer",
        summary="Handles repository HTTP routes and validates API request and response schemas.",
        cited_evidence_ids=tuple(item.evidence_id for item in candidate.evidence),
        limitations=("Runtime behavior is not confirmed by import evidence alone.",),
    )


def test_verifier_confirms_only_high_confidence_multi_file_citations() -> None:
    verifier = SubsystemEnrichmentVerifier()
    high_confidence = _candidate(confidence=0.85)
    low_confidence = _candidate(confidence=0.75)

    confirmed = verifier.verify(
        candidate=high_confidence,
        proposal=_proposal(high_confidence),
    )
    retained = verifier.verify(
        candidate=low_confidence,
        proposal=_proposal(low_confidence),
    )

    assert confirmed.status == "confirmed"
    assert confirmed.citation_coverage == 1.0
    assert retained.status == "candidate"


def test_verifier_rejects_evidence_outside_the_candidate() -> None:
    candidate = _candidate()
    proposal = SubsystemEnrichmentProposal(
        name="API Layer",
        summary="Handles repository HTTP routes and validates request and response schemas.",
        cited_evidence_ids=(uuid4(),),
    )

    with pytest.raises(SubsystemEnrichmentVerificationError, match="outside the candidate"):
        SubsystemEnrichmentVerifier().verify(candidate=candidate, proposal=proposal)


class FakeProvider:
    @property
    def info(self) -> SubsystemEnrichmentProviderInfo:
        return SubsystemEnrichmentProviderInfo(
            provider="test",
            model="structured-test-model",
            model_revision="v1",
        )

    async def enrich(self, candidate: SubsystemEnrichmentInput) -> SubsystemEnrichmentProposal:
        return _proposal(candidate)


class FakeReader:
    def __init__(self, candidates: tuple[SubsystemEnrichmentInput, ...]) -> None:
        self.candidates = candidates

    async def list_candidates(
        self, *, repository_id: object, repository_version_id: object
    ) -> tuple[SubsystemEnrichmentInput, ...]:
        return self.candidates


@pytest.mark.asyncio
async def test_builder_persists_verified_enrichment_and_model_evidence() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    graph_repository = MemoryGraphRepository()
    candidate = _candidate()
    persisted_evidence = []
    for evidence in candidate.evidence:
        file_node = await graph_repository.upsert_node(
            GraphNodeInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                entity_type=EntityType.FILE,
                canonical_key=f"file:{evidence.source_path}",
                name=evidence.source_path,
                provenance={"test": True},
                metadata={"path": evidence.source_path},
            )
        )
        persisted_evidence.append(
            SubsystemEvidenceInput(
                evidence_id=evidence.evidence_id,
                source_node_id=file_node.id,
                source_path=evidence.source_path,
                excerpt=evidence.excerpt,
                signals=evidence.signals,
            )
        )
    subsystem_node = await graph_repository.upsert_node(
        GraphNodeInput(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            entity_type=EntityType.SUBSYSTEM,
            canonical_key=candidate.canonical_key,
            name=candidate.current_name,
            description=candidate.current_description,
            knowledge_kind=KnowledgeKind.INFERRED,
            confidence=candidate.confidence,
            provenance={"algorithm": "subsystem-discovery-v1"},
            metadata=candidate.metadata,
        )
    )
    enriched_candidate = SubsystemEnrichmentInput(
        node_id=subsystem_node.id,
        canonical_key=candidate.canonical_key,
        current_name=candidate.current_name,
        current_description=candidate.current_description,
        confidence=candidate.confidence,
        member_paths=candidate.member_paths,
        signals=candidate.signals,
        evidence=tuple(persisted_evidence),
        metadata=candidate.metadata,
    )
    builder = SubsystemEnrichmentBuilder(
        graph_repository=graph_repository,
        reader=FakeReader((enriched_candidate,)),
        provider=FakeProvider(),
    )

    summary = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )

    assert summary.enriched == 1
    assert summary.confirmed == 1
    updated = graph_repository.nodes[(repository_id, candidate.canonical_key)]
    assert updated.name == "API Layer"
    assert updated.confidence == candidate.confidence
    assert updated.details["status"] == "confirmed"
    model_evidence = list(graph_repository.evidence.values())
    assert len(model_evidence) == 1
    assert model_evidence[0].evidence_type == EvidenceType.MODEL_INFERENCE


@pytest.mark.asyncio
async def test_builder_is_non_blocking_when_no_provider_is_configured() -> None:
    graph_repository = MemoryGraphRepository()
    reader: SubsystemEnrichmentReader = FakeReader((_candidate(),))
    summary = await SubsystemEnrichmentBuilder(
        graph_repository=graph_repository,
        reader=reader,
        provider=None,
    ).build(
        repository_id=uuid4(),
        repository_version_id=uuid4(),
    )

    assert summary.provider_available is False
    assert summary.enriched == 0
    assert not graph_repository.nodes
