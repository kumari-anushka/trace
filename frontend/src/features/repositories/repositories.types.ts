export type Repository = {
  id: string;
  github_id: number;
  owner: string;
  name: string;
  github_url: string;
  default_branch: string;
  description: string | null;
  homepage: string | null;
  primary_language: string | null;
  stars_count: number | null;
  forks_count: number | null;
  watchers_count: number | null;
  open_issues_count: number | null;
  archived: boolean | null;
  disabled: boolean | null;
  provider_created_at: string | null;
  provider_updated_at: string | null;
  provider_pushed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateRepositoryInput = {
  github_url: string;
};

export type RepositoryVersion = {
  id: string;
  repository_id: string;
  commit_sha: string;
  branch: string;
  languages: Record<string, number> | null;
  source_tree_sha: string | null;
  source_tree_truncated: boolean | null;
  created_at: string;
};

export type IngestionJobStatus =
  "pending" | "queued" | "running" | "completed" | "failed";

export type IngestionJob = {
  id: string;
  repository_version_id: string;
  status: IngestionJobStatus;
  progress: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type IngestionStageStatus =
  "pending" | "running" | "completed" | "failed" | "skipped";

export type IngestionStage = {
  id: string;
  ingestion_job_id: string;
  name: string;
  position: number;
  status: IngestionStageStatus;
  progress: number;
  error_message: string | null;
  output_summary: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type RepositoryIngestionStatus = {
  repository_id: string;
  ingestion_job: IngestionJob;
  stages: IngestionStage[];
};

export type RepositoryImportResponse = {
  repository: Repository;
  repository_version: RepositoryVersion;
  ingestion_job: IngestionJob;
};

export type RepositoryListResponse = {
  repositories: Repository[];
};
