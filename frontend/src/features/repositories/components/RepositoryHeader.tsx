import { ArrowLeft, ExternalLink, GitBranch } from "lucide-react";
import { Link } from "react-router-dom";

import type { Repository, RepositoryVersion } from "../repositories.types";

type RepositoryHeaderProps = {
  repository: Repository;
  latestVersion?: RepositoryVersion;
};

export function RepositoryHeader({
  repository,
  latestVersion,
}: RepositoryHeaderProps) {
  const branch = latestVersion?.branch ?? repository.default_branch;

  return (
    <>
      <Link className="repository-back" to="/">
        <ArrowLeft size={16} />
        Back
      </Link>

      <div className="repository-hero">
        <p className="repository-id">{repository.owner}</p>

        <h1>{repository.name}</h1>

        <div className="repository-hero__meta">
          <span>
            <GitBranch size={15} aria-hidden="true" />
            {branch}
          </span>

          <a href={repository.github_url} target="_blank" rel="noreferrer">
            View on GitHub
            <ExternalLink size={15} aria-hidden="true" />
          </a>
        </div>
      </div>
    </>
  );
}
