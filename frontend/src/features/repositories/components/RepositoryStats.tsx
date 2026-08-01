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
    { label: "Default branch", value: repository.default_branch },
    { label: "GitHub ID", value: String(repository.github_id) },
    {
      label: "Snapshots",
      value: isLoadingVersions ? "Loading…" : String(versions.length),
    },
    {
      label: "Latest commit",
      value: latestVersion?.commit_sha.slice(0, 7) ?? "Not available",
    },
    { label: "Added", value: formatDate(repository.created_at) },
    { label: "Last updated", value: formatDate(repository.updated_at) },
  ];

  return (
    <section className="repository-placeholder-grid">
      {cards.map((card) => (
        <article className="repository-placeholder-card" key={card.label}>
          <p>{card.label}</p>

          <h3 title={card.value}>{card.value}</h3>
        </article>
      ))}
    </section>
  );
}
