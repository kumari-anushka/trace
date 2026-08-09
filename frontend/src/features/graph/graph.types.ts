export type GraphEntityType =
  | "repository"
  | "repository_snapshot"
  | "directory"
  | "file"
  | "symbol"
  | "external_dependency"
  | "issue"
  | "pull_request"
  | "commit"
  | "release"
  | "discussion"
  | "person"
  | "label"
  | "subsystem"
  | "topic"
  | "decision"
  | "learning_step"
  | "architecture_summary";

export type GraphRelationshipType =
  | "CONTAINS"
  | "DECLARES"
  | "IMPORTS"
  | "CALLS"
  | "EXTENDS"
  | "IMPLEMENTS"
  | "DEPENDS_ON"
  | "MODIFIES"
  | "REFERENCES"
  | "RESOLVES"
  | "RELEASE_INCLUDES"
  | "PARENT_OF"
  | "AUTHORED"
  | "REVIEWED"
  | "PART_OF_SUBSYSTEM"
  | "ABOUT"
  | "DERIVED_FROM"
  | "IMPLEMENTED_BY"
  | "AFFECTS"
  | "RECOMMENDED_BEFORE"
  | "RELATED_TO";

export type GraphKnowledgeKind = "deterministic" | "derived" | "inferred";

export type GraphNode = {
  id: string;
  repository_id: string;
  repository_version_id: string | null;
  entity_type: GraphEntityType;
  canonical_key: string;
  name: string;
  description: string | null;
  knowledge_kind: GraphKnowledgeKind;
  confidence: number;
  provenance: Record<string, unknown>;
  metadata: Record<string, unknown>;
  ontology_version: string;
  created_at: string;
  updated_at: string;
};

export type GraphEdge = {
  id: string;
  repository_id: string;
  repository_version_id: string | null;
  source_node_id: string;
  target_node_id: string;
  relationship_type: GraphRelationshipType;
  knowledge_kind: GraphKnowledgeKind;
  confidence: number;
  provenance: Record<string, unknown>;
  metadata: Record<string, unknown>;
  ontology_version: string;
  created_at: string;
  updated_at: string;
};

export type GraphMetric = {
  id: string;
  repository_id: string;
  repository_version_id: string;
  node_id: string | null;
  metric_name: string;
  scope_key: string;
  value: number;
  algorithm_version: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type GraphResponse = {
  repository_id: string;
  repository_version_id: string;
  root_node_id: string | null;
  depth: number | null;
  node_count: number;
  edge_count: number;
  metric_count: number;
  nodes_truncated: boolean;
  edges_truncated: boolean;
  metrics_truncated: boolean;
  nodes: GraphNode[];
  edges: GraphEdge[];
  metrics: GraphMetric[];
};

export type GraphEvidence = {
  id: string;
  repository_id: string;
  repository_version_id: string | null;
  canonical_key: string;
  source_node_id: string;
  target_node_id: string | null;
  target_edge_id: string | null;
  evidence_type:
    | "artifact"
    | "source_span"
    | "graph_path"
    | "metric"
    | "provider_relation"
    | "model_inference";
  relationship: GraphRelationshipType | null;
  excerpt: string | null;
  source_url: string | null;
  start_line: number | null;
  end_line: number | null;
  confidence: number;
  provenance: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type GraphEvidenceListResponse = {
  repository_id: string;
  repository_version_id: string;
  count: number;
  truncated: boolean;
  evidence: GraphEvidence[];
};
