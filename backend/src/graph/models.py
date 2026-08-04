from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.ontology import ONTOLOGY_VERSION
from src.db.base import Base


class KnowledgeKind(StrEnum):
    DETERMINISTIC = "deterministic"
    DERIVED = "derived"
    INFERRED = "inferred"


class EvidenceType(StrEnum):
    ARTIFACT = "artifact"
    SOURCE_SPAN = "source_span"
    GRAPH_PATH = "graph_path"
    METRIC = "metric"
    PROVIDER_RELATION = "provider_relation"
    MODEL_INFERENCE = "model_inference"


class EntityType(StrEnum):
    REPOSITORY = "repository"
    REPOSITORY_SNAPSHOT = "repository_snapshot"
    DIRECTORY = "directory"
    FILE = "file"
    SYMBOL = "symbol"
    EXTERNAL_DEPENDENCY = "external_dependency"
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    COMMIT = "commit"
    RELEASE = "release"
    DISCUSSION = "discussion"
    PERSON = "person"
    LABEL = "label"
    SUBSYSTEM = "subsystem"
    TOPIC = "topic"
    DECISION = "decision"
    LEARNING_STEP = "learning_step"
    ARCHITECTURE_SUMMARY = "architecture_summary"


class RelationshipType(StrEnum):
    CONTAINS = "CONTAINS"
    DECLARES = "DECLARES"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    EXTENDS = "EXTENDS"
    IMPLEMENTS = "IMPLEMENTS"
    DEPENDS_ON = "DEPENDS_ON"
    MODIFIES = "MODIFIES"
    REFERENCES = "REFERENCES"
    RESOLVES = "RESOLVES"
    RELEASE_INCLUDES = "RELEASE_INCLUDES"
    PARENT_OF = "PARENT_OF"
    AUTHORED = "AUTHORED"
    REVIEWED = "REVIEWED"
    PART_OF_SUBSYSTEM = "PART_OF_SUBSYSTEM"
    ABOUT = "ABOUT"
    DERIVED_FROM = "DERIVED_FROM"
    IMPLEMENTED_BY = "IMPLEMENTED_BY"
    AFFECTS = "AFFECTS"
    RECOMMENDED_BEFORE = "RECOMMENDED_BEFORE"
    RELATED_TO = "RELATED_TO"


class GraphNode(Base):
    __tablename__ = "graph_nodes"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "canonical_key",
            name="uq_graph_nodes_repository_canonical_key",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repository_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    canonical_key: Mapped[str] = mapped_column(String(2000), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    knowledge_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    ontology_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ONTOLOGY_VERSION
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "source_node_id",
            "target_node_id",
            "relationship_type",
            name="uq_graph_edges_relation_identity",
        ),
        CheckConstraint("source_node_id <> target_node_id", name="no_self_loop"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repository_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    knowledge_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    ontology_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ONTOLOGY_VERSION
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class GraphEvidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "canonical_key",
            name="uq_evidence_repository_canonical_key",
        ),
        CheckConstraint(
            "(target_node_id IS NOT NULL) <> (target_edge_id IS NOT NULL)",
            name="exactly_one_target",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(
            "start_line IS NULL OR end_line IS NULL OR end_line >= start_line",
            name="line_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repository_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    canonical_key: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("graph_nodes.id", ondelete="CASCADE"), index=True
    )
    target_edge_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("graph_edges.id", ondelete="CASCADE"), index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    relationship: Mapped[str | None] = mapped_column(String(50))
    excerpt: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(2000))
    start_line: Mapped[int | None] = mapped_column(Integer)
    end_line: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class GraphMetric(Base):
    __tablename__ = "graph_metrics"
    __table_args__ = (
        UniqueConstraint(
            "repository_version_id",
            "metric_name",
            "scope_key",
            "algorithm_version",
            name="uq_graph_metrics_version_metric_scope_algorithm",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repository_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("graph_nodes.id", ondelete="CASCADE"), index=True
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(2000), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
