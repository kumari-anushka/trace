import { apiClient } from "../../../lib/api-client";
import type {
  CreateRepositoryInput,
  Repository,
  RepositoryImportResponse,
  RepositoryListResponse,
  RepositoryVersion,
} from "../repositories.types";

type DeleteRepositoryResponse = {
  message: string;
};

export async function getRepositories(): Promise<Repository[]> {
  const response = await apiClient.get<RepositoryListResponse>("/repositories");

  return response.data.repositories;
}

export async function getRepository(repositoryId: string): Promise<Repository> {
  const response = await apiClient.get<Repository>(
    `/repositories/${repositoryId}`,
  );

  return response.data;
}

export async function createRepository(
  input: CreateRepositoryInput,
): Promise<RepositoryImportResponse> {
  const response = await apiClient.post<RepositoryImportResponse>(
    "/repositories",
    input,
  );

  return response.data;
}

export async function deleteRepository(
  repositoryId: string,
): Promise<DeleteRepositoryResponse> {
  const response = await apiClient.delete<DeleteRepositoryResponse>(
    `/repositories/${repositoryId}`,
  );

  return response.data;
}

export async function getRepositoryVersions(
  repositoryId: string,
): Promise<RepositoryVersion[]> {
  const response = await apiClient.get<RepositoryVersion[]>(
    "/repository-versions",
    {
      params: {
        repository_id: repositoryId,
      },
    },
  );

  return response.data;
}
