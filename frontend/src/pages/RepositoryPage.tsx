import axios from "axios";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  CircleGauge,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import type { CSSProperties } from "react";
import { FaGithub } from "react-icons/fa";
import { Link, useParams } from "react-router-dom";

import { Footer } from "../components/layout/Footer";
import { Header } from "../components/layout/Header";
import { PageContainer } from "../components/layout/PageContainer";
import { RepositoryHeader } from "../features/repositories/components/RepositoryHeader";
import { RepositoryStats } from "../features/repositories/components/RepositoryStats";
import {
  useRepository,
  useRepositoryIngestion,
  useRepositoryVersions,
} from "../features/repositories/hooks/useRepositories";

export function RepositoryPage() {
  const { repositoryId } = useParams();
  const repositoryQuery = useRepository(repositoryId);
  const versionsQuery = useRepositoryVersions(repositoryId);
  const ingestionQuery = useRepositoryIngestion(repositoryId);
  const ingestionStatus = ingestionQuery.data?.ingestion_job.status;
  const ingestionProgress = ingestionQuery.data?.ingestion_job.progress ?? 0;

  const pipelineCopy =
    ingestionStatus === "completed"
      ? {
          eyebrow: "Atlas ready",
          title: "Your repository foundation is ready",
          description:
            "Trace has indexed this snapshot and prepared the repository context for exploration.",
          action: "View ingestion report",
        }
      : ingestionStatus === "failed"
        ? {
            eyebrow: "Action needed",
            title: "Ingestion needs your attention",
            description:
              "Review the pipeline report to see what interrupted this repository snapshot.",
            action: "Review pipeline",
          }
        : {
            eyebrow: "In progress",
            title: "Building your repository atlas",
            description:
              "Trace is turning the latest snapshot into structured, explorable context.",
            action: "Follow progress",
          };

  const isNotFound =
    axios.isAxiosError(repositoryQuery.error) &&
    repositoryQuery.error.response?.status === 404;

  return (
    <div className="app-shell">
      <Header />

      <main className="repository-page">
        <div className="repository-page__grid" aria-hidden="true" />
        <div className="repository-page__glow" aria-hidden="true" />
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
            <div className="repository-detail-content">
              <RepositoryHeader
                repository={repositoryQuery.data}
                latestVersion={versionsQuery.data?.[0]}
              />
              <RepositoryStats
                repository={repositoryQuery.data}
                versions={versionsQuery.data ?? []}
                isLoadingVersions={versionsQuery.isPending}
              />

              <div className="repository-dashboard">
                {ingestionStatus ? (
                  <Link
                    className="repository-pipeline"
                    data-status={ingestionStatus}
                    style={
                      {
                        "--repository-progress": `${ingestionProgress}%`,
                      } as CSSProperties
                    }
                    to={`/repositories/${repositoryQuery.data.id}/ingestion`}
                  >
                    <div className="repository-pipeline__topline">
                      <p>{pipelineCopy.eyebrow}</p>
                      <span>
                        {ingestionStatus === "completed" ? (
                          <CheckCircle2 size={15} aria-hidden="true" />
                        ) : ingestionStatus === "failed" ? (
                          <TriangleAlert size={15} aria-hidden="true" />
                        ) : (
                          <LoaderCircle size={15} aria-hidden="true" />
                        )}
                        {ingestionStatus}
                      </span>
                    </div>

                    <span
                      className="repository-pipeline__icon"
                      aria-hidden="true"
                    >
                      {ingestionStatus === "completed" ? (
                        <Sparkles size={24} />
                      ) : ingestionStatus === "failed" ? (
                        <TriangleAlert size={24} />
                      ) : (
                        <CircleGauge size={24} />
                      )}
                    </span>

                    <h2>{pipelineCopy.title}</h2>
                    <p className="repository-pipeline__description">
                      {pipelineCopy.description}
                    </p>

                    <div className="repository-pipeline__progress">
                      <div>
                        <span>Pipeline progress</span>
                        <strong>{ingestionProgress}%</strong>
                      </div>
                      <span className="repository-pipeline__track">
                        <span />
                      </span>
                    </div>

                    <span className="repository-pipeline__action">
                      {pipelineCopy.action}
                      <ArrowRight size={17} aria-hidden="true" />
                    </span>
                  </Link>
                ) : null}

                <aside
                  className="repository-details"
                  aria-labelledby="repository-details-title"
                >
                  <div className="repository-details__header">
                    <span aria-hidden="true">
                      <ShieldCheck size={19} />
                    </span>
                    <div>
                      <p>Source</p>
                      <h2 id="repository-details-title">Repository details</h2>
                    </div>
                  </div>

                  <dl>
                    <div>
                      <dt>Owner</dt>
                      <dd>{repositoryQuery.data.owner}</dd>
                    </div>
                    <div>
                      <dt>Default branch</dt>
                      <dd>{repositoryQuery.data.default_branch}</dd>
                    </div>
                    <div>
                      <dt>GitHub ID</dt>
                      <dd>{repositoryQuery.data.github_id}</dd>
                    </div>
                  </dl>

                  <a
                    href={repositoryQuery.data.github_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <FaGithub size={16} aria-hidden="true" />
                    View source repository
                    <ArrowUpRight size={15} aria-hidden="true" />
                  </a>
                </aside>
              </div>

              {versionsQuery.isError ? (
                <p className="repository-version-error" role="status">
                  Snapshot information is temporarily unavailable.
                </p>
              ) : null}
            </div>
          ) : null}
        </PageContainer>
      </main>

      <Footer />
    </div>
  );
}
