import { apiClient } from "../../../lib/api-client";
import type { CreateRepositoryInput, Repository } from "../repositories.types";

type DeleteRepositoryResponse = {
  message: string;
};

export async function getRepositories(): Promise<Repository[]> {
  const response = await apiClient.get<Repository[]>("/repositories");

  return response.data;
}

export async function createRepository(
  input: CreateRepositoryInput,
): Promise<Repository> {
  const response = await apiClient.post<Repository>("/repositories", input);

  return response.data;
}

export async function deleteRepository(
  repositoryId: number,
): Promise<DeleteRepositoryResponse> {
  const response = await apiClient.delete<DeleteRepositoryResponse>(
    `/repositories/${repositoryId}`,
  );

  return response.data;
}
