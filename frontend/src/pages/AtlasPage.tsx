import axios from "axios";
import {
  ArrowLeft,
  ArrowRight,
  Box,
  Boxes,
  Clock3,
  FileCode2,
  FileSearch,
  GitCommitHorizontal,
  GitPullRequest,
  Network,
  RefreshCw,
  Rocket,
  ShieldCheck,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Footer } from "../components/layout/Footer";
import { Header } from "../components/layout/Header";
import { PageContainer } from "../components/layout/PageContainer";
import { AtlasNav } from "../features/atlas/components/AtlasNav";
import { ConfidenceBadge } from "../features/atlas/components/ConfidenceBadge";
import {
  EvidenceDrawer,
  type EvidenceSelection,
} from "../features/atlas/components/EvidenceDrawer";
import {
  useAtlasEvidence,
  useAtlasGraph,
} from "../features/atlas/hooks/useAtlas";
import { GraphCanvas } from "../features/graph/components/GraphCanvas";
import type { GraphEdge, GraphNode } from "../features/graph/graph.types";
import {
  useRepository,
  useRepositoryVersions,
} from "../features/repositories/hooks/useRepositories";

export type AtlasView = "overview" | "architecture" | "subsystems" | "timeline";

type AtlasPageProps = { view: AtlasView };

function records(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> =>
          typeof item === "object" && item !== null,
      )
    : [];
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function number(value: unknown, fallback = 0): number {
  return typeof value === "number" ? value : fallback;
}

function timelineDate(node: GraphNode): string | null {
  const fields =
    node.entity_type === "release"
      ? ["published_at"]
      : node.entity_type === "commit"
        ? ["git_author_date", "git_committer_date"]
        : ["merged_at", "closed_at", "created_at", "updated_at"];
  for (const field of fields) {
    const value = node.metadata[field];
    if (typeof value === "string" && value) return value;
  }
  return null;
}

function eventIcon(type: GraphNode["entity_type"]) {
  if (type === "release") return <Rocket size={17} aria-hidden="true" />;
  if (type === "pull_request")
    return <GitPullRequest size={17} aria-hidden="true" />;
  if (type === "commit")
    return <GitCommitHorizontal size={17} aria-hidden="true" />;
  return <FileSearch size={17} aria-hidden="true" />;
}

export function AtlasPage({ view }: AtlasPageProps) {
  const { repositoryId, subsystemId } = useParams();
  const repositoryQuery = useRepository(repositoryId);
  const versionsQuery = useRepositoryVersions(repositoryId);
  const latestVersion = versionsQuery.data?.[0];
  const atlasQuery = useAtlasGraph(repositoryId, latestVersion?.id);
  const [selection, setSelection] = useState<EvidenceSelection | null>(null);
  const evidenceQuery = useAtlasEvidence(
    repositoryId,
    latestVersion?.id,
    selection !== null,
  );
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string | null>(
    null,
  );
  const graph = atlasQuery.data;
  const summaryNode = graph?.nodes.find(
    (node) => node.entity_type === "architecture_summary",
  );
  const subsystems = useMemo(
    () => graph?.nodes.filter((node) => node.entity_type === "subsystem") ?? [],
    [graph],
  );
  const events = useMemo(
    () =>
      (graph?.nodes ?? [])
        .filter((node) =>
          ["issue", "pull_request", "commit", "release"].includes(
            node.entity_type,
          ),
        )
        .sort((left, right) =>
          (timelineDate(right) ?? "").localeCompare(timelineDate(left) ?? ""),
        ),
    [graph],
  );
  const repositoryNotFound =
    axios.isAxiosError(repositoryQuery.error) &&
    repositoryQuery.error.response?.status === 404;
  const loading =
    repositoryQuery.isPending ||
    versionsQuery.isPending ||
    (latestVersion !== undefined && atlasQuery.isPending);
  const failed =
    repositoryQuery.isError ||
    versionsQuery.isError ||
    (latestVersion !== undefined && atlasQuery.isError);

  const titles: Record<AtlasView, [string, string]> = {
    overview: [
      "Software Atlas",
      "Understand the repository before asking a question.",
    ],
    architecture: [
      "Architecture",
      "See grounded components and their dependencies.",
    ],
    subsystems: [
      "Subsystems",
      "Inspect confirmed clusters and cautious candidates.",
    ],
    timeline: ["Timeline", "Follow the repository's recorded evolution."],
  };

  return (
    <div className="app-shell atlas-shell">
      <Header />
      <main className="atlas-page">
        <div className="atlas-page__grid" aria-hidden="true" />
        <PageContainer>
          <Link
            className="atlas-back"
            to={repositoryId ? `/repositories/${repositoryId}` : "/"}
          >
            <ArrowLeft size={15} aria-hidden="true" /> Repository
          </Link>

          {loading ? (
            <div className="atlas-state" aria-busy="true">
              <span /> <p>Loading the Software Atlas…</p>
            </div>
          ) : null}
          {failed ? (
            <div className="atlas-state" role="alert">
              <Network size={25} aria-hidden="true" />
              <h1>
                {repositoryNotFound
                  ? "Repository not found"
                  : "Atlas unavailable"}
              </h1>
              <p>
                {repositoryNotFound
                  ? "This repository may have been deleted."
                  : "Trace could not load this snapshot. Try again."}
              </p>
              {!repositoryNotFound ? (
                <button type="button" onClick={() => void atlasQuery.refetch()}>
                  <RefreshCw size={15} aria-hidden="true" /> Try again
                </button>
              ) : null}
            </div>
          ) : null}

          {!loading && !failed && repositoryQuery.data ? (
            <div className="atlas-content">
              <header className="atlas-hero">
                <div>
                  <p>{titles[view][0]}</p>
                  <h1>{titles[view][1]}</h1>
                  <span>
                    {repositoryQuery.data.owner}/{repositoryQuery.data.name}
                    {latestVersion
                      ? ` · ${latestVersion.commit_sha.slice(0, 8)}`
                      : ""}
                  </span>
                </div>
                {repositoryId ? <AtlasNav repositoryId={repositoryId} /> : null}
              </header>

              {graph?.nodes_truncated || graph?.edges_truncated ? (
                <p className="atlas-partial" role="status">
                  This is a bounded view. Some snapshot nodes or relationships
                  are not shown.
                </p>
              ) : null}

              {!latestVersion ? (
                <AtlasEmpty
                  title="No snapshot available"
                  body="Run ingestion before opening the Software Atlas."
                />
              ) : !summaryNode ? (
                <AtlasEmpty
                  title="Architecture analysis is not ready"
                  body="The snapshot exists, but its Week 4 analysis stages have not completed yet."
                />
              ) : view === "overview" ? (
                <Overview
                  summary={summaryNode}
                  subsystems={subsystems}
                  events={events}
                  repositoryId={repositoryId!}
                  onEvidence={setSelection}
                />
              ) : view === "architecture" ? (
                <Architecture
                  summary={summaryNode}
                  graphNodes={graph?.nodes ?? []}
                  graphEdges={graph?.edges ?? []}
                  selectedNodeId={selectedGraphNodeId}
                  onSelectNode={setSelectedGraphNodeId}
                  onEvidence={setSelection}
                />
              ) : view === "subsystems" ? (
                <Subsystems
                  subsystems={subsystems}
                  edges={graph?.edges ?? []}
                  repositoryId={repositoryId!}
                  subsystemId={subsystemId}
                  onEvidence={setSelection}
                />
              ) : (
                <Timeline
                  events={events}
                  edges={graph?.edges ?? []}
                  onEvidence={setSelection}
                />
              )}
            </div>
          ) : null}
        </PageContainer>
      </main>
      <Footer />
      <EvidenceDrawer
        selection={selection}
        evidence={evidenceQuery.data?.evidence ?? []}
        isLoading={evidenceQuery.isPending}
        truncated={evidenceQuery.data?.truncated ?? false}
        onClose={() => setSelection(null)}
      />
    </div>
  );
}

function Overview({
  summary,
  subsystems,
  events,
  repositoryId,
  onEvidence,
}: {
  summary: GraphNode;
  subsystems: GraphNode[];
  events: GraphNode[];
  repositoryId: string;
  onEvidence: (value: EvidenceSelection) => void;
}) {
  const entryPoints = records(summary.metadata.entry_points);
  const confirmed = subsystems.filter(
    (node) => node.metadata.status === "confirmed",
  );
  return (
    <div className="atlas-overview">
      <section className="atlas-summary-card">
        <div>
          <span>
            <ShieldCheck size={17} aria-hidden="true" /> Evidence-backed summary
          </span>
          <h2>{summary.description}</h2>
        </div>
        <button
          type="button"
          onClick={() =>
            onEvidence({
              title: "Architecture summary",
              factKind: "architecture",
            })
          }
        >
          Inspect evidence <ArrowRight size={15} aria-hidden="true" />
        </button>
      </section>
      <section className="atlas-stat-grid" aria-label="Atlas facts">
        <Stat
          label="Source files"
          value={number(summary.metadata.file_count)}
          icon={<FileCode2 />}
        />
        <Stat
          label="Likely entry points"
          value={entryPoints.length}
          icon={<Rocket />}
        />
        <Stat
          label="Confirmed subsystems"
          value={confirmed.length}
          icon={<Boxes />}
        />
        <Stat
          label="External dependencies"
          value={number(summary.metadata.external_dependency_count)}
          icon={<Box />}
        />
      </section>
      <div className="atlas-overview-grid">
        <section className="atlas-panel">
          <header>
            <div>
              <p>Components</p>
              <h2>Subsystem health</h2>
            </div>
            <Link to={`/repositories/${repositoryId}/subsystems`}>
              View all <ArrowRight size={14} />
            </Link>
          </header>
          {subsystems.length ? (
            subsystems.slice(0, 5).map((node) => (
              <Link
                className="atlas-row"
                key={node.id}
                to={`/repositories/${repositoryId}/subsystems/${node.id}`}
              >
                <span>
                  <Boxes size={16} />
                </span>
                <div>
                  <strong>{node.name}</strong>
                  <small>{number(node.metadata.member_count)} files</small>
                </div>
                <ConfidenceBadge
                  confidence={node.confidence}
                  status={text(node.metadata.status)}
                />
              </Link>
            ))
          ) : (
            <InlineEmpty text="No subsystem candidates were supported by enough signals." />
          )}
        </section>
        <section className="atlas-panel">
          <header>
            <div>
              <p>Evolution</p>
              <h2>Recent activity</h2>
            </div>
            <Link to={`/repositories/${repositoryId}/timeline`}>
              Timeline <ArrowRight size={14} />
            </Link>
          </header>
          {events.length ? (
            events.slice(0, 5).map((node) => (
              <article className="atlas-row" key={node.id}>
                <span>{eventIcon(node.entity_type)}</span>
                <div>
                  <strong>{node.name}</strong>
                  <small>{formatDate(timelineDate(node))}</small>
                </div>
              </article>
            ))
          ) : (
            <InlineEmpty text="No issues, pull requests, commits, or releases were captured." />
          )}
        </section>
      </div>
    </div>
  );
}

function Architecture({
  summary,
  graphNodes,
  graphEdges,
  selectedNodeId,
  onSelectNode,
  onEvidence,
}: {
  summary: GraphNode;
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  selectedNodeId: string | null;
  onSelectNode: (value: string) => void;
  onEvidence: (value: EvidenceSelection) => void;
}) {
  const entryPoints = records(summary.metadata.entry_points);
  const dependencies = records(summary.metadata.major_external_dependencies);
  const nodes = graphNodes.filter((node) =>
    ["architecture_summary", "subsystem", "external_dependency"].includes(
      node.entity_type,
    ),
  );
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = graphEdges.filter(
    (edge) =>
      nodeIds.has(edge.source_node_id) &&
      nodeIds.has(edge.target_node_id) &&
      ["DEPENDS_ON", "DERIVED_FROM"].includes(edge.relationship_type),
  );
  const selected = nodes.find((node) => node.id === selectedNodeId);
  const selectedFactEdge = selected
    ? edges.find(
        (edge) =>
          edge.relationship_type === "DERIVED_FROM" &&
          edge.target_node_id === selected.id,
      )
    : undefined;
  const limitations = Array.isArray(summary.metadata.limitations)
    ? summary.metadata.limitations.filter(
        (item): item is string => typeof item === "string",
      )
    : [];
  return (
    <div className="atlas-architecture">
      <section className="architecture-copy">
        <div>
          <p>Generated summary</p>
          <h2>{summary.description}</h2>
        </div>
        <ul>
          {limitations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
      <section className="architecture-map atlas-panel">
        <header>
          <div>
            <p>Bounded graph</p>
            <h2>Subsystem and dependency map</h2>
          </div>
          <span>
            {nodes.length} nodes · {edges.length} edges
          </span>
        </header>
        {nodes.length > 1 ? (
          <div className="architecture-map__stage">
            <GraphCanvas
              nodes={nodes}
              edges={edges}
              metrics={[]}
              selectedNodeId={selectedNodeId}
              onSelectNode={onSelectNode}
            />
            <aside>
              {selected ? (
                <>
                  <p>{selected.entity_type.replaceAll("_", " ")}</p>
                  <h3>{selected.name}</h3>
                  <ConfidenceBadge
                    confidence={selected.confidence}
                    status={text(selected.metadata.status)}
                  />
                  <button
                    type="button"
                    onClick={() =>
                      onEvidence(
                        selected.entity_type === "architecture_summary"
                          ? {
                              title: selected.name,
                              factKind: "architecture",
                            }
                          : {
                              title: selected.name,
                              nodeId: selected.id,
                              edgeId: selectedFactEdge?.id,
                            },
                      )
                    }
                  >
                    View evidence
                  </button>
                </>
              ) : (
                <>
                  <Network size={20} />
                  <h3>Select a component</h3>
                  <p>Choose a node to inspect its confidence and evidence.</p>
                </>
              )}
            </aside>
          </div>
        ) : (
          <InlineEmpty text="No confirmed subsystem graph is available yet." />
        )}
        {edges.length ? (
          <div
            className="architecture-edge-list"
            aria-label="Subsystem dependency list"
          >
            {edges
              .filter((edge) => edge.relationship_type === "DEPENDS_ON")
              .map((edge) => {
                const source = nodes.find(
                  (node) => node.id === edge.source_node_id,
                );
                const target = nodes.find(
                  (node) => node.id === edge.target_node_id,
                );
                return (
                  <button
                    key={edge.id}
                    type="button"
                    onClick={() =>
                      onEvidence({
                        title: `${source?.name ?? "Subsystem"} depends on ${target?.name ?? "subsystem"}`,
                        edgeId: edge.id,
                      })
                    }
                  >
                    <strong>{source?.name}</strong>
                    <span>depends on</span>
                    <strong>{target?.name}</strong>
                    <ConfidenceBadge confidence={edge.confidence} />
                  </button>
                );
              })}
          </div>
        ) : null}
      </section>
      <div className="architecture-facts">
        <section className="atlas-panel">
          <header>
            <div>
              <p>Launch surfaces</p>
              <h2>Likely entry points</h2>
            </div>
          </header>
          {entryPoints.length ? (
            entryPoints.map((item) => (
              <button
                className="fact-card"
                type="button"
                key={text(item.node_id)}
                onClick={() =>
                  onEvidence({
                    title: text(item.path),
                    factKind: "entry_point",
                    path: text(item.path),
                  })
                }
              >
                <Rocket size={16} />
                <span>
                  <strong>{text(item.path)}</strong>
                  <small>
                    {Array.isArray(item.signals) && item.signals.length > 1
                      ? "Multiple signals"
                      : "Deterministic signals"}
                  </small>
                </span>
                <ConfidenceBadge confidence={number(item.confidence)} />
              </button>
            ))
          ) : (
            <InlineEmpty text="No entry point reached the confidence threshold." />
          )}
        </section>
        <section className="atlas-panel">
          <header>
            <div>
              <p>Imports</p>
              <h2>Major external dependencies</h2>
            </div>
          </header>
          {dependencies.length ? (
            dependencies.map((item) => (
              <button
                className="fact-card"
                type="button"
                key={text(item.node_id)}
                onClick={() =>
                  onEvidence({
                    title: text(item.name),
                    factKind: "external_dependency",
                    path: text(item.name),
                  })
                }
              >
                <Box size={16} />
                <span>
                  <strong>{text(item.name)}</strong>
                  <small>
                    {text(item.ecosystem, "package")} ·{" "}
                    {number(item.importer_count)} importing files
                  </small>
                </span>
              </button>
            ))
          ) : (
            <InlineEmpty text="No non-standard-library dependencies were imported." />
          )}
        </section>
      </div>
    </div>
  );
}

function Subsystems({
  subsystems,
  edges,
  repositoryId,
  subsystemId,
  onEvidence,
}: {
  subsystems: GraphNode[];
  edges: GraphEdge[];
  repositoryId: string;
  subsystemId?: string;
  onEvidence: (value: EvidenceSelection) => void;
}) {
  const selected = subsystemId
    ? subsystems.find((node) => node.id === subsystemId)
    : undefined;
  if (subsystemId && !selected) {
    return (
      <AtlasEmpty
        title="Subsystem not found"
        body="This cluster may have been pruned after the snapshot was rebuilt."
      />
    );
  }
  if (selected) {
    const memberPaths = Array.isArray(selected.metadata.member_paths)
      ? selected.metadata.member_paths.filter(
          (item): item is string => typeof item === "string",
        )
      : [];
    const connected = edges.filter(
      (edge) =>
        edge.relationship_type === "DEPENDS_ON" &&
        (edge.source_node_id === selected.id ||
          edge.target_node_id === selected.id),
    );
    return (
      <div className="subsystem-detail">
        <Link to={`/repositories/${repositoryId}/subsystems`}>
          <ArrowLeft size={14} /> All subsystems
        </Link>
        <section className="subsystem-detail__hero">
          <div>
            <p>{text(selected.metadata.status, "candidate")}</p>
            <h2>{selected.name}</h2>
            <span>
              {selected.description ?? "Evidence-backed repository cluster."}
            </span>
          </div>
          <ConfidenceBadge
            confidence={selected.confidence}
            status={text(selected.metadata.status)}
          />
        </section>
        <div className="subsystem-detail__grid">
          <section className="atlas-panel">
            <header>
              <div>
                <p>Membership</p>
                <h2>Files in this cluster</h2>
              </div>
              <span>{memberPaths.length}</span>
            </header>
            {memberPaths.length ? (
              <ul className="member-list">
                {memberPaths.map((path) => (
                  <li key={path}>
                    <FileCode2 size={14} />
                    {path}
                  </li>
                ))}
              </ul>
            ) : (
              <InlineEmpty text="No member paths were persisted." />
            )}
          </section>
          <section className="atlas-panel">
            <header>
              <div>
                <p>Connections</p>
                <h2>Subsystem dependencies</h2>
              </div>
            </header>
            {connected.length ? (
              connected.map((edge) => {
                const otherId =
                  edge.source_node_id === selected.id
                    ? edge.target_node_id
                    : edge.source_node_id;
                const other = subsystems.find((node) => node.id === otherId);
                return (
                  <button
                    className="dependency-row"
                    type="button"
                    key={edge.id}
                    onClick={() =>
                      onEvidence({
                        title: `${selected.name} dependency`,
                        edgeId: edge.id,
                      })
                    }
                  >
                    <Network size={15} />
                    <span>
                      {edge.source_node_id === selected.id
                        ? "Depends on"
                        : "Used by"}{" "}
                      <strong>{other?.name ?? "Subsystem"}</strong>
                    </span>
                    <ConfidenceBadge confidence={edge.confidence} />
                  </button>
                );
              })
            ) : (
              <InlineEmpty text="No cross-subsystem imports were detected." />
            )}
          </section>
        </div>
        <button
          className="inspect-evidence"
          type="button"
          onClick={() =>
            onEvidence({ title: selected.name, nodeId: selected.id })
          }
        >
          <FileSearch size={15} /> Inspect discovery evidence
        </button>
      </div>
    );
  }
  return (
    <section className="subsystem-list">
      {subsystems.length ? (
        subsystems.map((node) => (
          <Link
            key={node.id}
            to={`/repositories/${repositoryId}/subsystems/${node.id}`}
          >
            <div>
              <span>
                <Boxes size={18} />
              </span>
              <p>{text(node.metadata.status, "candidate")}</p>
            </div>
            <h2>{node.name}</h2>
            <p>
              {node.description ??
                "Repository files grouped by deterministic signals."}
            </p>
            <footer>
              <small>{number(node.metadata.member_count)} files</small>
              <ConfidenceBadge
                confidence={node.confidence}
                status={text(node.metadata.status)}
              />
            </footer>
          </Link>
        ))
      ) : (
        <AtlasEmpty
          title="No supported subsystem clusters"
          body="Low-signal groupings are intentionally omitted instead of being presented as architecture."
        />
      )}
    </section>
  );
}

function Timeline({
  events,
  edges,
  onEvidence,
}: {
  events: GraphNode[];
  edges: GraphEdge[];
  onEvidence: (value: EvidenceSelection) => void;
}) {
  if (!events.length)
    return (
      <AtlasEmpty
        title="No historical artifacts"
        body="This bounded snapshot did not capture issues, pull requests, commits, or releases."
      />
    );
  return (
    <section className="timeline">
      <div className="timeline__rail" aria-hidden="true" />
      {events.map((node) => {
        const relatedEdge = edges.find(
          (edge) =>
            edge.source_node_id === node.id || edge.target_node_id === node.id,
        );
        const url = text(node.metadata.html_url);
        return (
          <article key={node.id}>
            <div className="timeline__marker">
              {eventIcon(node.entity_type)}
            </div>
            <div className="timeline__date">
              {formatDate(timelineDate(node))}
            </div>
            <div className="timeline__card">
              <header>
                <span>{node.entity_type.replaceAll("_", " ")}</span>
                {typeof node.metadata.state === "string" ? (
                  <small>{node.metadata.state}</small>
                ) : null}
              </header>
              <h2>{node.name}</h2>
              {node.description ? <p>{node.description}</p> : null}
              <footer>
                {relatedEdge ? (
                  <button
                    type="button"
                    onClick={() =>
                      onEvidence({
                        title: node.name,
                        edgeId: relatedEdge.id,
                        nodeId: node.id,
                      })
                    }
                  >
                    <FileSearch size={14} /> Evidence
                  </button>
                ) : null}
                {url ? (
                  <a href={url} target="_blank" rel="noreferrer">
                    Open on GitHub <ArrowRight size={14} />
                  </a>
                ) : null}
              </footer>
            </div>
          </article>
        );
      })}
    </section>
  );
}

function Stat({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: React.ReactElement;
}) {
  return (
    <article>
      <span>{icon}</span>
      <p>{label}</p>
      <strong>{value.toLocaleString()}</strong>
    </article>
  );
}

function AtlasEmpty({ title, body }: { title: string; body: string }) {
  return (
    <section className="atlas-empty">
      <Network size={27} aria-hidden="true" />
      <p>Bounded snapshot</p>
      <h2>{title}</h2>
      <span>{body}</span>
    </section>
  );
}

function InlineEmpty({ text: value }: { text: string }) {
  return (
    <div className="atlas-inline-empty">
      <Clock3 size={18} aria-hidden="true" />
      <p>{value}</p>
    </div>
  );
}

function formatDate(value: string | null) {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? "Date unavailable"
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}
