import axios from "axios";
import { Link, useParams } from "react-router-dom";

import { Footer } from "../components/layout/Footer";
import { Header } from "../components/layout/Header";
import { PageContainer } from "../components/layout/PageContainer";
import { RepositoryHeader } from "../features/repositories/components/RepositoryHeader";
import { RepositoryStats } from "../features/repositories/components/RepositoryStats";
import {
  useRepository,
  useRepositoryVersions,
} from "../features/repositories/hooks/useRepositories";

export function RepositoryPage() {
  const { repositoryId } = useParams();
  const repositoryQuery = useRepository(repositoryId);
  const versionsQuery = useRepositoryVersions(repositoryId);

  const isNotFound =
    axios.isAxiosError(repositoryQuery.error) &&
    repositoryQuery.error.response?.status === 404;

  return (
    <div className="app-shell">
      <Header />

      <main className="repository-page">
        <PageContainer>
          {repositoryQuery.isPending ? (
            <div className="repository-detail-state" aria-busy="true">
              <span className="repository-detail-state__spinner" />
              <p>Loading repository…</p>
            </div>
          ) : null}

          {repositoryQuery.isError ? (
            <div className="repository-detail-state" role="alert">
              <h1>
                {isNotFound
                  ? "Repository not found"
                  : "Could not load repository"}
              </h1>
              <p>
                {isNotFound
                  ? "This repository may have been deleted."
                  : "Trace could not reach the API."}
              </p>

              <div className="repository-detail-state__actions">
                {!isNotFound ? (
                  <button
                    type="button"
                    onClick={() => repositoryQuery.refetch()}
                  >
                    Try again
                  </button>
                ) : null}
                <Link to="/">Return home</Link>
              </div>
            </div>
          ) : null}

          {repositoryQuery.data ? (
            <>
              <RepositoryHeader
                repository={repositoryQuery.data}
                latestVersion={versionsQuery.data?.[0]}
              />
              <RepositoryStats
                repository={repositoryQuery.data}
                versions={versionsQuery.data ?? []}
                isLoadingVersions={versionsQuery.isPending}
              />

              {versionsQuery.isError ? (
                <p className="repository-version-error" role="status">
                  Snapshot information is temporarily unavailable.
                </p>
              ) : null}
            </>
          ) : null}
        </PageContainer>
      </main>

      <Footer />
    </div>
  );
}
