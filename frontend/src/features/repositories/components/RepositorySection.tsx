import { PageContainer } from "../../../components/layout/PageContainer";
import { useRepositories } from "../hooks/useRepositories";
import { RepositoryCard } from "./RepositoryCard";
import { RepositoryEmptyState } from "./RepositoryEmptyState";
import { RepositorySkeleton } from "./RepositorySkeleton";

export function RepositorySection() {
  const repositoriesQuery = useRepositories();
  const repositories = repositoriesQuery.data ?? [];

  return (
    <section
      className="repository-section"
      id="repositories"
      aria-labelledby="repositories-title"
    >
      <PageContainer>
        <div className="repository-section__header">
          <div>
            <p className="repository-section__eyebrow">Your workspace</p>
            <h2 id="repositories-title">Repositories</h2>
          </div>

          {!repositoriesQuery.isLoading && repositories.length > 0 ? (
            <span className="repository-section__count">
              {repositories.length}
            </span>
          ) : null}
        </div>

        {repositoriesQuery.isLoading ? (
          <div
            className="repository-grid"
            aria-label="Loading repositories"
            aria-busy="true"
          >
            {Array.from({ length: 3 }, (_, index) => (
              <RepositorySkeleton key={index} />
            ))}
          </div>
        ) : null}

        {repositoriesQuery.isError ? (
          <div className="repository-section__error" role="alert">
            <h3>Could not load repositories</h3>
            <p>Trace could not reach the API.</p>

            <button type="button" onClick={() => repositoriesQuery.refetch()}>
              Try again
            </button>
          </div>
        ) : null}

        {repositoriesQuery.isSuccess && repositories.length === 0 ? (
          <RepositoryEmptyState />
        ) : null}

        {repositoriesQuery.isSuccess && repositories.length > 0 ? (
          <div className="repository-grid">
            {repositories.map((repository) => (
              <RepositoryCard key={repository.id} repository={repository} />
            ))}
          </div>
        ) : null}
      </PageContainer>
    </section>
  );
}
