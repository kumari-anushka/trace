import { ArrowLeft, ArrowUpRight, FolderGit2, GitBranch } from "lucide-react";
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
    <header className="repository-header">
      <Link className="repository-back" to="/#repositories">
        <ArrowLeft size={16} />
        All repositories
      </Link>

      <div className="repository-hero">
        <div className="repository-hero__content">
          <p className="repository-hero__eyebrow">
            <span aria-hidden="true" />
            Repository atlas
          </p>

          <div className="repository-hero__title-row">
            <span className="repository-hero__mark" aria-hidden="true">
              <FolderGit2 size={29} strokeWidth={1.7} />
            </span>
            <div>
              <p className="repository-hero__owner">{repository.owner}</p>
              <h1>{repository.name}</h1>
            </div>
          </div>

          <p className="repository-hero__description">
            A living technical map of your codebase, grounded in the latest
            repository snapshot.
          </p>

          <div className="repository-hero__actions">
            <span className="repository-branch">
              <GitBranch size={15} aria-hidden="true" />
              {branch}
            </span>

            <a
              className="repository-github-button"
              href={repository.github_url}
              target="_blank"
              rel="noreferrer"
            >
              Open in GitHub
              <ArrowUpRight size={16} aria-hidden="true" />
            </a>
          </div>
        </div>

        <div className="repository-hero__visual" aria-hidden="true">
          <span className="repository-hero__orbit repository-hero__orbit--one" />
          <span className="repository-hero__orbit repository-hero__orbit--two" />
          <span className="repository-hero__node repository-hero__node--one" />
          <span className="repository-hero__node repository-hero__node--two" />
          <span className="repository-hero__node repository-hero__node--three" />
          <span className="repository-hero__monogram">
            {repository.name.slice(0, 1).toUpperCase()}
          </span>
        </div>
      </div>
    </header>
  );
}
