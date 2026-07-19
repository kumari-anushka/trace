import { GitBranch, GitPullRequestArrow, Network } from "lucide-react";

import { PageContainer } from "../layout/PageContainer";

const features = [
  {
    title: "Architecture",
    description:
      "Discover systems, modules, and relationships across the repository.",
    icon: Network,
  },
  {
    title: "Timeline",
    description:
      "Understand how the repository evolved through commits and releases.",
    icon: GitBranch,
  },
  {
    title: "Decisions",
    description:
      "Connect commits and pull requests to the architectural decisions behind them.",
    icon: GitPullRequestArrow,
  },
];

export function HomeFeatures() {
  return (
    <section className="home-features" aria-label="Trace capabilities">
      <PageContainer>
        <div className="home-features__grid">
          {features.map(({ title, description, icon: Icon }) => (
            <article className="home-feature-card" key={title}>
              <span className="home-feature-card__icon" aria-hidden="true">
                <Icon size={21} strokeWidth={1.8} />
              </span>

              <h2>{title}</h2>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </PageContainer>
    </section>
  );
}
