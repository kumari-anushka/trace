import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createRepository,
  deleteRepository,
  getRepository,
  getRepositoryIngestionStatus,
  getRepositories,
  getRepositoryVersions,
} from "../api/repositories.api";
import type {
  CreateRepositoryInput,
  IngestionJobStatus,
  Repository,
  RepositoryIngestionStatus,
} from "../repositories.types";

const ACTIVE_INGESTION_STATUSES: ReadonlySet<IngestionJobStatus> = new Set([
  "pending",
  "queued",
  "running",
]);

function retryUnlessNotFound(failureCount: number, error: unknown): boolean {
  if (axios.isAxiosError(error) && error.response?.status === 404) {
    return false;
  }

  return failureCount < 3;
}

export const repositoryQueryKeys = {
  all: ["repositories"] as const,
  detail: (repositoryId: string) => ["repositories", repositoryId] as const,
  versions: (repositoryId: string) =>
    ["repositories", repositoryId, "versions"] as const,
  ingestion: (repositoryId: string) =>
    ["repositories", repositoryId, "ingestion"] as const,
};

export function useRepositories() {
  return useQuery({
    queryKey: repositoryQueryKeys.all,
    queryFn: getRepositories,
  });
}

export function useRepository(repositoryId: string | undefined) {
  return useQuery({
    queryKey: repositoryQueryKeys.detail(repositoryId ?? ""),
    queryFn: () => getRepository(repositoryId!),
    enabled: Boolean(repositoryId),
    retry: retryUnlessNotFound,
  });
}

export function useRepositoryVersions(repositoryId: string | undefined) {
  return useQuery({
    queryKey: repositoryQueryKeys.versions(repositoryId ?? ""),
    queryFn: () => getRepositoryVersions(repositoryId!),
    enabled: Boolean(repositoryId),
  });
}

export function useRepositoryIngestion(repositoryId: string | undefined) {
  return useQuery({
    queryKey: repositoryQueryKeys.ingestion(repositoryId ?? ""),
    queryFn: () => getRepositoryIngestionStatus(repositoryId!),
    enabled: Boolean(repositoryId),
    retry: retryUnlessNotFound,
    refetchInterval: (query) => {
      if (query.state.error) {
        return false;
      }

      const status = query.state.data?.ingestion_job.status;

      return status && ACTIVE_INGESTION_STATUSES.has(status) ? 1_500 : false;
    },
  });
}

export function useCreateRepository() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateRepositoryInput) => createRepository(input),
    onSuccess: async (result) => {
      queryClient.setQueryData<Repository[]>(
        repositoryQueryKeys.all,
        (repositories = []) => [
          result.repository,
          ...repositories.filter(
            (repository) => repository.id !== result.repository.id,
          ),
        ],
      );
      queryClient.setQueryData(
        repositoryQueryKeys.detail(result.repository.id),
        result.repository,
      );
      queryClient.setQueryData(
        repositoryQueryKeys.versions(result.repository.id),
        [result.repository_version],
      );
      queryClient.setQueryData<RepositoryIngestionStatus>(
        repositoryQueryKeys.ingestion(result.repository.id),
        {
          repository_id: result.repository.id,
          ingestion_job: result.ingestion_job,
          stages: [],
        },
      );

      await queryClient.invalidateQueries({
        queryKey: repositoryQueryKeys.all,
        exact: true,
      });
    },
  });
}

export function useDeleteRepository() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (repositoryId: string) => deleteRepository(repositoryId),

    onSuccess: async (_response, repositoryId) => {
      queryClient.setQueryData<Repository[]>(
        repositoryQueryKeys.all,
        (repositories) =>
          repositories?.filter(
            (repository) => repository.id !== repositoryId,
          ) ?? [],
      );

      await queryClient.invalidateQueries({
        queryKey: repositoryQueryKeys.all,
        exact: true,
      });

      queryClient.removeQueries({
        queryKey: repositoryQueryKeys.detail(repositoryId),
      });
    },
  });
}
