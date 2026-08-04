import axios from "axios";
import { ArrowLeft, GitBranch, Network, RefreshCw } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Footer } from "../components/layout/Footer";
import { Header } from "../components/layout/Header";
import { PageContainer } from "../components/layout/PageContainer";
import { GraphExplorer } from "../features/graph/components/GraphExplorer";
import { useRepositoryGraph } from "../features/graph/hooks/useRepositoryGraph";
import {
  useRepository,
  useRepositoryVersions,
} from "../features/repositories/hooks/useRepositories";

export function RepositoryGraphPage() {
  const { repositoryId } = useParams();
  const repositoryQuery = useRepository(repositoryId);
  const versionsQuery = useRepositoryVersions(repositoryId);
  const latestVersion = versionsQuery.data?.[0];
  const graphQuery = useRepositoryGraph(repositoryId, latestVersion?.id);
  const repositoryNotFound =
    axios.isAxiosError(repositoryQuery.error) &&
    repositoryQuery.error.response?.status === 404;

  const isLoading =
    repositoryQuery.isPending ||
    versionsQuery.isPending ||
    (latestVersion !== undefined && graphQuery.isPending);
  const hasError =
    repositoryQuery.isError ||
    versionsQuery.isError ||
    (latestVersion !== undefined && graphQuery.isError);

  return (
    <div className="app-shell graph-shell">
      <Header />

      <main className="graph-page">
        <div className="graph-page__grid" aria-hidden="true" />
        <div className="graph-page__glow" aria-hidden="true" />
        <PageContainer>
          <Link
            className="graph-back"
            to={repositoryId ? `/repositories/${repositoryId}` : "/"}
          >
            <ArrowLeft size={15} aria-hidden="true" />
            Repository overview
          </Link>

          {isLoading ? (
            <div className="graph-page-state" aria-busy="true">
              <span className="graph-page-state__spinner" />
              <p>Loading repository graph…</p>
            </div>
          ) : null}

          {hasError ? (
            <div className="graph-page-state" role="alert">
              <span aria-hidden="true">
                <Network size={25} />
              </span>
              <h1>
                {repositoryNotFound
                  ? "Repository not found"
                  : "Could not load the graph"}
              </h1>
              <p>
                {repositoryNotFound
                  ? "This repository may have been deleted."
                  : "Trace could not load this snapshot graph. Try the request again."}
              </p>
              <div>
                {!repositoryNotFound ? (
                  <button
                    type="button"
                    onClick={() => {
                      void Promise.all([
                        repositoryQuery.refetch(),
                        versionsQuery.refetch(),
                        graphQuery.refetch(),
                      ]);
                    }}
                  >
                    <RefreshCw size={15} aria-hidden="true" />
                    Try again
                  </button>
                ) : null}
                <Link to="/">Return home</Link>
              </div>
            </div>
          ) : null}

          {!isLoading && !hasError && repositoryQuery.data ? (
            <div className="graph-page-content">
              <header className="graph-hero">
                <div className="graph-hero__copy">
                  <p className="graph-hero__eyebrow">
                    <span aria-hidden="true">
                      <Network size={16} />
                    </span>
                    Architecture explorer
                  </p>
                  <h1>
                    See how <span>{repositoryQuery.data.name}</span> fits
                    together.
                  </h1>
                  <p>
                    Explore deterministic repository structure and imports.
                    Select a node for its provenance, confidence, and structural
                    metrics.
                  </p>
                  <div className="graph-hero__repository">
                    <span>{repositoryQuery.data.owner}</span>
                    <strong>/</strong>
                    <span>{repositoryQuery.data.name}</span>
                  </div>
                </div>

                {latestVersion ? (
                  <div className="graph-snapshot-card">
                    <span aria-hidden="true">
                      <GitBranch size={19} />
                    </span>
                    <p>Active snapshot</p>
                    <strong>{latestVersion.branch}</strong>
                    <code>{latestVersion.commit_sha.slice(0, 12)}</code>
                    <small>Immutable repository snapshot</small>
                  </div>
                ) : null}
              </header>

              {latestVersion && graphQuery.data ? (
                <GraphExplorer graph={graphQuery.data} />
              ) : (
                <section
                  className="graph-empty"
                  aria-labelledby="graph-no-snapshot-title"
                >
                  <span aria-hidden="true">
                    <GitBranch size={27} />
                  </span>
                  <p>Repository snapshot</p>
                  <h2 id="graph-no-snapshot-title">No snapshot is available</h2>
                  <p>
                    Run repository ingestion before opening the architecture
                    graph.
                  </p>
                </section>
              )}
            </div>
          ) : null}
        </PageContainer>
      </main>

      <Footer />
    </div>
  );
}
