import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createRepository,
  deleteRepository,
  getRepository,
  getRepositories,
  getRepositoryVersions,
} from "../api/repositories.api";
import type { CreateRepositoryInput, Repository } from "../repositories.types";

export const repositoryQueryKeys = {
  all: ["repositories"] as const,
  detail: (repositoryId: string) => ["repositories", repositoryId] as const,
  versions: (repositoryId: string) =>
    ["repositories", repositoryId, "versions"] as const,
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
  });
}

export function useRepositoryVersions(repositoryId: string | undefined) {
  return useQuery({
    queryKey: repositoryQueryKeys.versions(repositoryId ?? ""),
    queryFn: () => getRepositoryVersions(repositoryId!),
    enabled: Boolean(repositoryId),
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
