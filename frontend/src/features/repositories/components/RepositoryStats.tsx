import {
  CalendarDays,
  GitBranch,
  GitCommitHorizontal,
  Layers3,
} from "lucide-react";

import type { Repository, RepositoryVersion } from "../repositories.types";

type RepositoryStatsProps = {
  repository: Repository;
  versions: RepositoryVersion[];
  isLoadingVersions: boolean;
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export function RepositoryStats({
  repository,
  versions,
  isLoadingVersions,
}: RepositoryStatsProps) {
  const latestVersion = versions[0];
  const cards = [
    {
      label: "Default branch",
      value: repository.default_branch,
      detail: "Primary source branch",
      icon: GitBranch,
    },
    {
      label: "Snapshots indexed",
      value: isLoadingVersions ? "Loading…" : String(versions.length),
      detail:
        versions.length === 1 ? "Repository version" : "Repository versions",
      icon: Layers3,
    },
    {
      label: "Latest commit",
      value: latestVersion?.commit_sha.slice(0, 7) ?? "Not available",
      detail: latestVersion
        ? `Captured ${formatDate(latestVersion.created_at)}`
        : "No snapshot captured yet",
      icon: GitCommitHorizontal,
    },
    {
      label: "Connected",
      value: formatDate(repository.created_at),
      detail: `GitHub repository #${repository.github_id}`,
      icon: CalendarDays,
    },
  ];

  return (
    <section className="repository-stats" aria-label="Repository overview">
      {cards.map((card) => {
        const Icon = card.icon;

        return (
          <article className="repository-stat" key={card.label}>
            <span className="repository-stat__icon" aria-hidden="true">
              <Icon size={18} strokeWidth={1.8} />
            </span>
            <div>
              <p className="repository-stat__label">{card.label}</p>
              <h2 title={card.value}>{card.value}</h2>
              <p className="repository-stat__detail">{card.detail}</p>
            </div>
          </article>
        );
      })}
    </section>
  );
}
