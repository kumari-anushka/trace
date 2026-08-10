import { apiClient } from "../../../lib/api-client";
import type { RepositoryQueryResponse } from "../ask.types";

export async function queryRepository(
  repositoryId: string,
  question: string,
): Promise<RepositoryQueryResponse> {
  const response = await apiClient.post<RepositoryQueryResponse>(
    `/repositories/${repositoryId}/query`,
    { question },
  );
  return response.data;
}
