import { useQuery } from "@tanstack/react-query";

import { getRepositoryGraph } from "../api/graph.api";

export const graphQueryKeys = {
  snapshot: (repositoryId: string, repositoryVersionId: string) =>
    [
      "repositories",
      repositoryId,
      "versions",
      repositoryVersionId,
      "graph",
    ] as const,
};

export function useRepositoryGraph(
  repositoryId: string | undefined,
  repositoryVersionId: string | undefined,
) {
  return useQuery({
    queryKey: graphQueryKeys.snapshot(
      repositoryId ?? "",
      repositoryVersionId ?? "",
    ),
    queryFn: () => getRepositoryGraph(repositoryId!, repositoryVersionId!),
    enabled: Boolean(repositoryId && repositoryVersionId),
  });
}
