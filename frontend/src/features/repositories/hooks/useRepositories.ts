import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createRepository,
  deleteRepository,
  getRepositories,
} from "../api/repositories.api";
import type { CreateRepositoryInput, Repository } from "../repositories.types";

export const repositoryQueryKeys = {
  all: ["repositories"] as const,
};

export function useRepositories() {
  return useQuery({
    queryKey: repositoryQueryKeys.all,
    queryFn: getRepositories,
  });
}

export function useCreateRepository() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateRepositoryInput) => createRepository(input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: repositoryQueryKeys.all,
      });
    },
  });
}

export function useDeleteRepository() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (repositoryId: number) => deleteRepository(repositoryId),

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
      });
    },
  });
}
