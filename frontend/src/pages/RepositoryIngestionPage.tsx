import axios from "axios";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Circle,
  Clock3,
  ExternalLink,
  GitBranch,
  GitCommitHorizontal,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  XCircle,
} from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { Footer } from "../components/layout/Footer";
import { Header } from "../components/layout/Header";
import { PageContainer } from "../components/layout/PageContainer";
import {
  useRepository,
  useRepositoryIngestion,
  useRepositoryVersions,
} from "../features/repositories/hooks/useRepositories";
import type {
  IngestionJobStatus,
  IngestionStage,
  IngestionStageStatus,
} from "../features/repositories/repositories.types";

const JOB_COPY: Record<
  IngestionJobStatus,
  { eyebrow: string; title: string; description: string }
> = {
  pending: {
    eyebrow: "Preparing ingestion",
    title: "Getting the workspace ready",
    description:
      "Trace is creating a durable job before handing the snapshot to a worker.",
  },
  queued: {
    eyebrow: "Queued for analysis",
    title: "Your repository is in line",
    description:
      "The snapshot is safely recorded. A worker will begin preparing it shortly.",
  },
  running: {
    eyebrow: "Building your atlas",
    title: "Mapping the repository",
    description:
      "Trace is turning this fixed snapshot into a reliable foundation for the Software Atlas.",
  },
  completed: {
    eyebrow: "Ingestion complete",
    title: "The foundation is ready",
    description:
      "The repository snapshot passed every foundation check and is ready to explore.",
  },
  failed: {
    eyebrow: "Ingestion stopped",
    title: "The snapshot needs attention",
    description:
      "Trace preserved the failure details so you can understand what happened and try again safely.",
  },
};

const STATUS_LABELS: Record<IngestionJobStatus, string> = {
  pending: "Preparing",
  queued: "Queued",
  running: "In progress",
  completed: "Complete",
  failed: "Failed",
};

function formatStageName(name: string): string {
  return name
    .split("_")
    .filter(Boolean)
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(" ");
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("en", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function getStageIcon(status: IngestionStageStatus): ReactNode {
  switch (status) {
    case "completed":
      return <Check size={16} aria-hidden="true" />;
    case "failed":
      return <XCircle size={17} aria-hidden="true" />;
    case "running":
      return <LoaderCircle size={17} aria-hidden="true" />;
    case "skipped":
      return <ArrowRight size={16} aria-hidden="true" />;
    default:
      return <Circle size={14} aria-hidden="true" />;
  }
}

function StageRow({ stage }: { stage: IngestionStage }) {
  const summaryEntries = Object.entries(stage.output_summary ?? {}).filter(
    (entry): entry is [string, number] =>
      !entry[0].startsWith("_") && typeof entry[1] === "number",
  );

  return (
    <li className="ingestion-stage" data-status={stage.status}>
      <span className="ingestion-stage__rail" aria-hidden="true" />
      <span className="ingestion-stage__icon">
        {getStageIcon(stage.status)}
      </span>

      <div className="ingestion-stage__content">
        <div className="ingestion-stage__heading">
          <div>
            <p>Stage {stage.position + 1}</p>
            <h3>{formatStageName(stage.name)}</h3>
          </div>
          <span>{stage.status}</span>
        </div>

        {stage.status === "running" ? (
          <div
            className="ingestion-stage__progress"
            role="progressbar"
            aria-label={`${formatStageName(stage.name)} progress`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={stage.progress}
          >
            <span style={{ width: `${stage.progress}%` }} />
          </div>
        ) : null}

        {stage.error_message ? (
          <p className="ingestion-stage__error">{stage.error_message}</p>
        ) : null}

        {summaryEntries.length > 0 ? (
          <dl className="ingestion-stage__summary">
            {summaryEntries.map(([name, value]) => (
              <div key={name}>
                <dt>{formatStageName(name)}</dt>
                <dd>{value.toLocaleString()}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
    </li>
  );
}

function IngestionLoadingState() {
  return (
    <div
      className="ingestion-loading"
      aria-busy="true"
      aria-label="Loading ingestion progress"
    >
      <div className="ingestion-loading__line ingestion-loading__line--short" />
      <div className="ingestion-loading__line ingestion-loading__line--title" />
      <div className="ingestion-loading__line ingestion-loading__line--copy" />
      <div className="ingestion-loading__grid">
        <div className="ingestion-loading__panel" />
        <div className="ingestion-loading__panel ingestion-loading__panel--small" />
      </div>
    </div>
  );
}

export function RepositoryIngestionPage() {
  const { repositoryId } = useParams();
  const repositoryQuery = useRepository(repositoryId);
  const versionsQuery = useRepositoryVersions(repositoryId);
  const ingestionQuery = useRepositoryIngestion(repositoryId);

  const repository = repositoryQuery.data;
  const ingestion = ingestionQuery.data;
  const latestVersion = versionsQuery.data?.[0];
  const status = ingestion?.ingestion_job.status;
  const progress = Math.min(
    100,
    Math.max(0, ingestion?.ingestion_job.progress ?? 0),
  );
  const copy = status ? JOB_COPY[status] : null;
  const isActive =
    status === "pending" || status === "queued" || status === "running";
  const isNotFound =
    (axios.isAxiosError(repositoryQuery.error) &&
      repositoryQuery.error.response?.status === 404) ||
    (axios.isAxiosError(ingestionQuery.error) &&
      ingestionQuery.error.response?.status === 404);
  const hasError = repositoryQuery.isError || ingestionQuery.isError;
  const isLoading =
    !hasError &&
    (repositoryQuery.isPending ||
      ingestionQuery.isPending ||
      !repository ||
      !ingestion);
  const progressStyle = {
    "--ingestion-progress": `${progress * 3.6}deg`,
  } as CSSProperties;

  function refetchPage() {
    void Promise.all([
      repositoryQuery.refetch(),
      versionsQuery.refetch(),
      ingestionQuery.refetch(),
    ]);
  }

  return (
    <div className="app-shell ingestion-shell">
      <Header />

      <main className="ingestion-page">
        <div className="ingestion-page__glow" aria-hidden="true" />
        <PageContainer>
          <Link
            className="ingestion-back"
            to={repositoryId ? `/repositories/${repositoryId}` : "/"}
          >
            <ArrowLeft size={16} aria-hidden="true" />
            Repository details
          </Link>

          {isLoading ? <IngestionLoadingState /> : null}

          {hasError ? (
            <section className="ingestion-error-state" role="alert">
              <span className="ingestion-error-state__icon">
                <TriangleAlert size={24} aria-hidden="true" />
              </span>
              <p className="ingestion-error-state__eyebrow">
                Unable to load progress
              </p>
              <h1>
                {isNotFound
                  ? "Ingestion not found"
                  : "Progress is temporarily unavailable"}
              </h1>
              <p>
                {isNotFound
                  ? "This repository or its ingestion job may have been removed."
                  : "Trace could not reach the API. Your saved progress is still safe."}
              </p>
              <div className="ingestion-error-state__actions">
                {!isNotFound ? (
                  <button type="button" onClick={refetchPage}>
                    <RefreshCw size={16} aria-hidden="true" />
                    Try again
                  </button>
                ) : null}
                <Link to="/">Return home</Link>
              </div>
            </section>
          ) : null}

          {repository && ingestion && status && copy ? (
            <div className="ingestion-content" aria-live="polite">
              <section className="ingestion-hero">
                <div className="ingestion-hero__copy">
                  <div className="ingestion-hero__eyebrow">
                    <span className="ingestion-hero__spark">
                      <Sparkles size={14} aria-hidden="true" />
                    </span>
                    {copy.eyebrow}
                  </div>

                  <h1>{copy.title}</h1>
                  <p>{copy.description}</p>

                  <div className="ingestion-repository">
                    <span>{repository.owner}</span>
                    <strong>/</strong>
                    <span>{repository.name}</span>
                  </div>
                </div>

                <div
                  className="ingestion-progress-orbit"
                  data-status={status}
                  style={progressStyle}
                  role="progressbar"
                  aria-label="Overall ingestion progress"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={progress}
                >
                  <div className="ingestion-progress-orbit__track">
                    <div className="ingestion-progress-orbit__center">
                      <strong>{progress}</strong>
                      <span>percent</span>
                    </div>
                  </div>
                </div>
              </section>

              <div className="ingestion-layout">
                <section className="ingestion-panel ingestion-panel--progress">
                  <div className="ingestion-panel__header">
                    <div>
                      <p className="ingestion-panel__eyebrow">Live progress</p>
                      <h2>Ingestion pipeline</h2>
                    </div>

                    <span className="ingestion-status" data-status={status}>
                      <span aria-hidden="true" />
                      {STATUS_LABELS[status]}
                    </span>
                  </div>

                  <div className="ingestion-overall-progress">
                    <div>
                      <span>Overall progress</span>
                      <strong>{progress}%</strong>
                    </div>
                    <div
                      className="ingestion-overall-progress__track"
                      aria-hidden="true"
                    >
                      <span style={{ width: `${progress}%` }} />
                    </div>
                  </div>

                  <div className="ingestion-stage-heading">
                    <h3>Pipeline stages</h3>
                    <span>
                      {ingestion.stages.length}{" "}
                      {ingestion.stages.length === 1 ? "stage" : "stages"}
                    </span>
                  </div>

                  {ingestion.stages.length ? (
                    <ol className="ingestion-stages">
                      {ingestion.stages.map((stage) => (
                        <StageRow key={stage.id} stage={stage} />
                      ))}
                    </ol>
                  ) : (
                    <div className="ingestion-stage-waiting">
                      <span>
                        <Clock3 size={17} aria-hidden="true" />
                      </span>
                      <div>
                        <h3>Waiting for a worker</h3>
                        <p>
                          The first pipeline stage will appear here
                          automatically.
                        </p>
                      </div>
                    </div>
                  )}

                  {status === "failed" ? (
                    <div className="ingestion-failure" role="status">
                      <TriangleAlert size={18} aria-hidden="true" />
                      <div>
                        <strong>Ingestion could not finish</strong>
                        <p>
                          {ingestion.ingestion_job.error_message ??
                            "The worker stopped before completing this snapshot."}
                        </p>
                      </div>
                    </div>
                  ) : null}

                  {status === "completed" ? (
                    <div className="ingestion-complete">
                      <span>
                        <CheckCircle2 size={21} aria-hidden="true" />
                      </span>
                      <div>
                        <strong>Foundation complete</strong>
                        <p>
                          The persisted snapshot is ready for the next Atlas
                          capabilities.
                        </p>
                      </div>
                      <Link to={`/repositories/${repository.id}`}>
                        View repository
                        <ArrowRight size={16} aria-hidden="true" />
                      </Link>
                    </div>
                  ) : null}

                  <div className="ingestion-sync-line">
                    {isActive ? (
                      <>
                        <RefreshCw size={13} aria-hidden="true" />
                        Updating automatically
                      </>
                    ) : (
                      <>
                        <CheckCircle2 size={13} aria-hidden="true" />
                        Final status saved
                      </>
                    )}
                    <span>
                      Last update{" "}
                      {formatTime(ingestion.ingestion_job.updated_at)}
                    </span>
                  </div>
                </section>

                <aside className="ingestion-sidebar">
                  <section className="ingestion-panel ingestion-snapshot">
                    <div className="ingestion-panel__header">
                      <div>
                        <p className="ingestion-panel__eyebrow">
                          Source of truth
                        </p>
                        <h2>Snapshot</h2>
                      </div>
                      <ShieldCheck size={20} aria-hidden="true" />
                    </div>

                    <dl className="ingestion-snapshot__list">
                      <div>
                        <dt>
                          <GitBranch size={15} aria-hidden="true" />
                          Branch
                        </dt>
                        <dd>
                          {latestVersion?.branch ?? repository.default_branch}
                        </dd>
                      </div>
                      <div>
                        <dt>
                          <GitCommitHorizontal size={15} aria-hidden="true" />
                          Commit
                        </dt>
                        <dd title={latestVersion?.commit_sha}>
                          {latestVersion?.commit_sha.slice(0, 9) ??
                            "Resolving…"}
                        </dd>
                      </div>
                      <div>
                        <dt>Job ID</dt>
                        <dd title={ingestion.ingestion_job.id}>
                          {ingestion.ingestion_job.id.slice(0, 8)}
                        </dd>
                      </div>
                    </dl>

                    <a
                      className="ingestion-github-link"
                      href={repository.github_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open source on GitHub
                      <ExternalLink size={15} aria-hidden="true" />
                    </a>
                  </section>

                  <section className="ingestion-persistence-note">
                    <span>
                      <ShieldCheck size={17} aria-hidden="true" />
                    </span>
                    <div>
                      <strong>Safe to leave this page</strong>
                      <p>
                        Progress is stored in PostgreSQL and will be restored
                        when you return.
                      </p>
                    </div>
                  </section>
                </aside>
              </div>
            </div>
          ) : null}
        </PageContainer>
      </main>

      <Footer />
    </div>
  );
}
