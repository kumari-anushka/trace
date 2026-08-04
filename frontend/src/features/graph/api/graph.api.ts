import { apiClient } from "../../../lib/api-client";
import type {
  GraphEntityType,
  GraphRelationshipType,
  GraphResponse,
} from "../graph.types";

const ARCHITECTURE_NODE_TYPES: GraphEntityType[] = [
  "repository_snapshot",
  "directory",
  "file",
  "external_dependency",
];

const ARCHITECTURE_RELATIONSHIPS: GraphRelationshipType[] = [
  "CONTAINS",
  "IMPORTS",
];

export async function getRepositoryGraph(
  repositoryId: string,
  repositoryVersionId: string,
): Promise<GraphResponse> {
  const params = new URLSearchParams({
    limit: "250",
    edge_limit: "1000",
    metric_limit: "1000",
  });

  for (const entityType of ARCHITECTURE_NODE_TYPES) {
    params.append("entity_type", entityType);
  }
  for (const relationship of ARCHITECTURE_RELATIONSHIPS) {
    params.append("relationship_type", relationship);
  }
  params.append("metric_name", "degree_centrality");
  params.append("metric_name", "community_membership");

  const response = await apiClient.get<GraphResponse>(
    `/repositories/${repositoryId}/versions/${repositoryVersionId}/graph`,
    { params },
  );

  return response.data;
}
