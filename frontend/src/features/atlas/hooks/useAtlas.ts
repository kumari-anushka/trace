import { useQuery } from "@tanstack/react-query";

import { getAtlasEvidence, getAtlasGraph } from "../api/atlas.api";

export function useAtlasGraph(
  repositoryId: string | undefined,
  repositoryVersionId: string | undefined,
) {
  return useQuery({
    queryKey: ["atlas", repositoryId, repositoryVersionId, "graph"],
    queryFn: () => getAtlasGraph(repositoryId!, repositoryVersionId!),
    enabled: Boolean(repositoryId && repositoryVersionId),
  });
}

export function useAtlasEvidence(
  repositoryId: string | undefined,
  repositoryVersionId: string | undefined,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["atlas", repositoryId, repositoryVersionId, "evidence"],
    queryFn: () => getAtlasEvidence(repositoryId!, repositoryVersionId!),
    enabled: Boolean(enabled && repositoryId && repositoryVersionId),
  });
}
