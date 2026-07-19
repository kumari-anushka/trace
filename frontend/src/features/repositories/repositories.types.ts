export type Repository = {
  id: number;
  owner: string;
  name: string;
  github_url: string;
  created_at: string;
};

export type CreateRepositoryInput = {
  github_url: string;
};
