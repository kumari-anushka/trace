import { apiClient } from "../../../lib/api-client";
import type {
  GraphEntityType,
  GraphEvidenceListResponse,
  GraphRelationshipType,
  GraphResponse,
} from "../../graph/graph.types";

const atlasNodeTypes: GraphEntityType[] = [
  "architecture_summary",
  "subsystem",
  "external_dependency",
  "issue",
  "pull_request",
  "commit",
  "release",
];

const intelligenceNodeTypes: GraphEntityType[] = ["decision", "person"];
const intelligenceMetricNames = [
  "contributor_activity_score",
  "contributor_authored_pull_requests",
  "contributor_reviews",
  "contributor_commits",
  "contributor_subsystem_files",
  "contributor_recency",
];

const atlasRelationships: GraphRelationshipType[] = [
  "DEPENDS_ON",
  "DERIVED_FROM",
  "REFERENCES",
  "RESOLVES",
  "RELEASE_INCLUDES",
];

export async function getAtlasGraph(
  repositoryId: string,
  repositoryVersionId: string,
): Promise<GraphResponse> {
  const atlasParams = new URLSearchParams({
    limit: "500",
    edge_limit: "2000",
    metric_limit: "1",
    include_metrics: "false",
  });
  atlasNodeTypes.forEach((value) => atlasParams.append("entity_type", value));
  atlasRelationships.forEach((value) =>
    atlasParams.append("relationship_type", value),
  );
  const intelligenceParams = new URLSearchParams({
    limit: "500",
    edge_limit: "1",
    metric_limit: "1000",
    include_metrics: "true",
  });
  intelligenceNodeTypes.forEach((value) =>
    intelligenceParams.append("entity_type", value),
  );
  intelligenceMetricNames.forEach((value) =>
    intelligenceParams.append("metric_name", value),
  );
  const path = `/repositories/${repositoryId}/versions/${repositoryVersionId}/graph`;
  const [atlasResponse, intelligenceResponse] = await Promise.all([
    apiClient.get<GraphResponse>(path, { params: atlasParams }),
    apiClient.get<GraphResponse>(path, { params: intelligenceParams }),
  ]);
  const atlas = atlasResponse.data;
  const intelligence = intelligenceResponse.data;
  return {
    ...atlas,
    node_count: atlas.nodes.length + intelligence.nodes.length,
    edge_count: atlas.edges.length + intelligence.edges.length,
    metric_count: intelligence.metrics.length,
    nodes_truncated: atlas.nodes_truncated || intelligence.nodes_truncated,
    edges_truncated: atlas.edges_truncated || intelligence.edges_truncated,
    metrics_truncated: intelligence.metrics_truncated,
    nodes: [...atlas.nodes, ...intelligence.nodes],
    edges: [...atlas.edges, ...intelligence.edges],
    metrics: intelligence.metrics,
  };
}

export async function getAtlasEvidence(
  repositoryId: string,
  repositoryVersionId: string,
): Promise<GraphEvidenceListResponse> {
  const response = await apiClient.get<GraphEvidenceListResponse>(
    `/repositories/${repositoryId}/versions/${repositoryVersionId}/graph/evidence`,
    { params: { limit: 500 } },
  );
  return response.data;
}
