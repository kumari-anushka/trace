import { useMutation } from "@tanstack/react-query";

import { queryRepository } from "../api/ask.api";

export function useRepositoryQuery(repositoryId: string | undefined) {
  return useMutation({
    mutationFn: (question: string) => queryRepository(repositoryId!, question),
  });
}
