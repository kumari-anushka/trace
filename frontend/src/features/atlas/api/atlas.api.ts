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
  const params = new URLSearchParams({
    limit: "500",
    edge_limit: "2000",
    metric_limit: "500",
    include_metrics: "false",
  });
  atlasNodeTypes.forEach((value) => params.append("entity_type", value));
  atlasRelationships.forEach((value) =>
    params.append("relationship_type", value),
  );
  const response = await apiClient.get<GraphResponse>(
    `/repositories/${repositoryId}/versions/${repositoryVersionId}/graph`,
    { params },
  );
  return response.data;
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
