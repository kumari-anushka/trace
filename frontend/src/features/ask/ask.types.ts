export type RetrievalMode = "metadata" | "vector" | "graph";

export type QueryClaim = {
  text: string;
  citation_ids: string[];
};

export type QueryCitation = {
  id: string;
  title: string;
  source_type: string;
  source_url: string | null;
  excerpt: string;
  retrieval_modes: RetrievalMode[];
};

export type RepositoryQueryResponse = {
  repository_id: string;
  repository_version_id: string;
  question: string;
  answer: string;
  claims: QueryClaim[];
  citations: QueryCitation[];
  limitations: string[];
  retrieval_modes: RetrievalMode[];
  grounded: boolean;
};
