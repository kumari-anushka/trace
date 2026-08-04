import {
  AlertTriangle,
  Braces,
  Box,
  FileCode2,
  FolderTree,
  Network,
  Search,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type {
  GraphEdge,
  GraphMetric,
  GraphNode,
  GraphRelationshipType,
  GraphResponse,
} from "../graph.types";
import { GraphCanvas } from "./GraphCanvas";

type GraphExplorerProps = {
  graph: GraphResponse;
};

const relationshipLabels: Record<"CONTAINS" | "IMPORTS", string> = {
  CONTAINS: "Structure",
  IMPORTS: "Imports",
};

const entityLabels: Record<string, string> = {
  repository_snapshot: "Snapshot",
  directory: "Directory",
  file: "File",
  external_dependency: "Dependency",
};

function textValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function nodePath(node: GraphNode): string | null {
  return textValue(node.metadata.path);
}

function metricForNode(
  metrics: GraphMetric[],
  nodeId: string,
  metricName: string,
): GraphMetric | undefined {
  return metrics.find(
    (metric) => metric.node_id === nodeId && metric.metric_name === metricName,
  );
}

function nodeIcon(node: GraphNode) {
  if (node.entity_type === "directory") {
    return <FolderTree size={16} aria-hidden="true" />;
  }
  if (node.entity_type === "file") {
    return <FileCode2 size={16} aria-hidden="true" />;
  }
  if (node.entity_type === "external_dependency") {
    return <Box size={16} aria-hidden="true" />;
  }
  return <Braces size={16} aria-hidden="true" />;
}

export function GraphExplorer({ graph }: GraphExplorerProps) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [visibleRelationships, setVisibleRelationships] = useState<
    Set<GraphRelationshipType>
  >(new Set(["CONTAINS", "IMPORTS"]));

  const nodesById = useMemo(
    () => new Map(graph.nodes.map((node) => [node.id, node])),
    [graph.nodes],
  );
  const filteredEdges = useMemo(
    () =>
      graph.edges.filter((edge) =>
        visibleRelationships.has(edge.relationship_type),
      ),
    [graph.edges, visibleRelationships],
  );
  const selectedNode = selectedNodeId
    ? (nodesById.get(selectedNodeId) ?? null)
    : null;
  const searchResults = useMemo(() => {
    const normalized = searchQuery.trim().toLowerCase();
    if (!normalized) {
      return [];
    }
    return graph.nodes
      .filter((node) => {
        const path = nodePath(node);
        return (
          node.name.toLowerCase().includes(normalized) ||
          path?.toLowerCase().includes(normalized) ||
          node.entity_type.toLowerCase().includes(normalized)
        );
      })
      .slice(0, 7);
  }, [graph.nodes, searchQuery]);

  useEffect(() => {
    if (selectedNodeId && nodesById.has(selectedNodeId)) {
      return;
    }
    const centralityMetrics = graph.metrics
      .filter(
        (metric) =>
          metric.metric_name === "degree_centrality" && metric.node_id,
      )
      .sort((left, right) => right.value - left.value);
    setSelectedNodeId(
      centralityMetrics[0]?.node_id ?? graph.nodes[0]?.id ?? null,
    );
  }, [graph.metrics, graph.nodes, nodesById, selectedNodeId]);

  function toggleRelationship(relationship: GraphRelationshipType) {
    setVisibleRelationships((current) => {
      const next = new Set(current);
      if (next.has(relationship)) {
        next.delete(relationship);
      } else {
        next.add(relationship);
      }
      return next;
    });
  }

  function selectNode(nodeId: string) {
    setSelectedNodeId(nodeId);
    setSearchQuery("");
  }

  if (graph.nodes.length === 0) {
    return (
      <section className="graph-empty" aria-labelledby="graph-empty-title">
        <span aria-hidden="true">
          <Network size={28} />
        </span>
        <p>Snapshot graph</p>
        <h2 id="graph-empty-title">No graph facts yet</h2>
        <p>
          Trace has not persisted architecture nodes for this snapshot. If
          ingestion is still running, this view will become available after the
          graph stages complete.
        </p>
      </section>
    );
  }

  const selectedCentrality = selectedNode
    ? metricForNode(graph.metrics, selectedNode.id, "degree_centrality")
    : undefined;
  const selectedCommunity = selectedNode
    ? metricForNode(graph.metrics, selectedNode.id, "community_membership")
    : undefined;
  const selectedLanguage = selectedNode
    ? textValue(selectedNode.metadata.language)
    : null;
  const selectedProvider = selectedNode
    ? (textValue(selectedNode.provenance.provider) ??
      textValue(selectedNode.provenance.parser))
    : null;

  return (
    <div className="graph-explorer">
      {graph.nodes_truncated ||
      graph.edges_truncated ||
      graph.metrics_truncated ? (
        <div className="graph-truncation" role="status">
          <AlertTriangle size={16} aria-hidden="true" />
          <p>
            This is a bounded view. Refine the graph or open a node neighborhood
            before treating it as complete.
          </p>
        </div>
      ) : null}

      <section
        className="graph-workspace"
        aria-labelledby="graph-workspace-title"
      >
        <header className="graph-workspace__header">
          <div>
            <p>Deterministic architecture</p>
            <h2 id="graph-workspace-title">Repository map</h2>
          </div>
          <dl
            className="graph-workspace__stats"
            aria-label="Graph result counts"
          >
            <div>
              <dt>Nodes</dt>
              <dd>{graph.node_count}</dd>
            </div>
            <div>
              <dt>Edges</dt>
              <dd>{graph.edge_count}</dd>
            </div>
            <div>
              <dt>Metrics</dt>
              <dd>{graph.metric_count}</dd>
            </div>
          </dl>
        </header>

        <div className="graph-controls">
          <div className="graph-search">
            <Search size={16} aria-hidden="true" />
            <label className="sr-only" htmlFor="graph-node-search">
              Find a graph node
            </label>
            <input
              id="graph-node-search"
              type="search"
              value={searchQuery}
              placeholder="Find a file or directory"
              autoComplete="off"
              onChange={(event) => setSearchQuery(event.target.value)}
            />
            {searchResults.length > 0 ? (
              <div
                className="graph-search__results"
                aria-label="Matching graph nodes"
              >
                {searchResults.map((node) => (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => selectNode(node.id)}
                  >
                    <span aria-hidden="true">{nodeIcon(node)}</span>
                    <span>
                      <strong>{node.name}</strong>
                      <small>
                        {nodePath(node) ?? entityLabels[node.entity_type]}
                      </small>
                    </span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <div
            className="graph-relationship-filters"
            aria-label="Visible relationships"
          >
            {(["CONTAINS", "IMPORTS"] as const).map((relationship) => (
              <button
                key={relationship}
                type="button"
                aria-pressed={visibleRelationships.has(relationship)}
                onClick={() => toggleRelationship(relationship)}
              >
                <span data-relationship={relationship} aria-hidden="true" />
                {relationshipLabels[relationship]}
              </button>
            ))}
          </div>
        </div>

        <div className="graph-stage">
          <div className="graph-visual" aria-label="Visual repository graph">
            <GraphCanvas
              nodes={graph.nodes}
              edges={filteredEdges}
              metrics={graph.metrics}
              selectedNodeId={selectedNodeId}
              onSelectNode={selectNode}
            />
            <div className="graph-legend" aria-hidden="true">
              <span data-type="snapshot">Snapshot</span>
              <span data-type="directory">Directory</span>
              <span data-type="file">File</span>
              <span data-type="dependency">Dependency</span>
            </div>
          </div>

          <aside className="graph-inspector" aria-live="polite">
            {selectedNode ? (
              <>
                <div className="graph-inspector__type">
                  <span aria-hidden="true">{nodeIcon(selectedNode)}</span>
                  {entityLabels[selectedNode.entity_type] ??
                    selectedNode.entity_type}
                </div>
                <h3>{selectedNode.name}</h3>
                <p className="graph-inspector__path">
                  {nodePath(selectedNode) ?? selectedNode.canonical_key}
                </p>
                {selectedNode.description ? (
                  <p>{selectedNode.description}</p>
                ) : null}

                <dl className="graph-inspector__metrics">
                  <div>
                    <dt>Centrality</dt>
                    <dd>
                      {selectedCentrality
                        ? selectedCentrality.value.toFixed(3)
                        : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt>Community</dt>
                    <dd>
                      {typeof selectedCommunity?.metadata.community_index ===
                      "number"
                        ? `#${selectedCommunity.metadata.community_index + 1}`
                        : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt>Confidence</dt>
                    <dd>{Math.round(selectedNode.confidence * 100)}%</dd>
                  </div>
                </dl>

                <dl className="graph-inspector__facts">
                  {selectedLanguage ? (
                    <div>
                      <dt>Language</dt>
                      <dd>{selectedLanguage}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt>Knowledge</dt>
                    <dd>{selectedNode.knowledge_kind}</dd>
                  </div>
                  {selectedProvider ? (
                    <div>
                      <dt>Source</dt>
                      <dd>{selectedProvider}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt>Ontology</dt>
                    <dd>{selectedNode.ontology_version}</dd>
                  </div>
                </dl>
              </>
            ) : (
              <div className="graph-inspector__empty">
                <Network size={22} aria-hidden="true" />
                <h3>Select a node</h3>
                <p>Choose a node from search, the graph, or the edge list.</p>
              </div>
            )}
          </aside>
        </div>
      </section>

      <AccessibleEdgeList
        edges={filteredEdges}
        nodesById={nodesById}
        onSelectNode={selectNode}
      />
    </div>
  );
}

type AccessibleEdgeListProps = {
  edges: GraphEdge[];
  nodesById: Map<string, GraphNode>;
  onSelectNode: (nodeId: string) => void;
};

function AccessibleEdgeList({
  edges,
  nodesById,
  onSelectNode,
}: AccessibleEdgeListProps) {
  return (
    <section
      className="graph-edge-list"
      aria-labelledby="graph-edge-list-title"
    >
      <div className="graph-edge-list__header">
        <div>
          <p>Text alternative</p>
          <h2 id="graph-edge-list-title">Relationship index</h2>
        </div>
        <span>{edges.length} visible relationships</span>
      </div>

      {edges.length === 0 ? (
        <p className="graph-edge-list__empty">
          No relationships match the active filters.
        </p>
      ) : (
        <div className="graph-edge-table-wrap">
          <table>
            <caption className="sr-only">
              Source nodes, relationship types, and target nodes in the visible
              graph
            </caption>
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">Relationship</th>
                <th scope="col">Target</th>
                <th scope="col">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {edges.map((edge) => {
                const source = nodesById.get(edge.source_node_id);
                const target = nodesById.get(edge.target_node_id);
                return (
                  <tr key={edge.id}>
                    <td>
                      <button
                        type="button"
                        onClick={() => onSelectNode(edge.source_node_id)}
                      >
                        {source?.name ?? "Unknown node"}
                      </button>
                      <small>
                        {source ? nodePath(source) : edge.source_node_id}
                      </small>
                    </td>
                    <td>
                      <span data-relationship={edge.relationship_type}>
                        {edge.relationship_type}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        onClick={() => onSelectNode(edge.target_node_id)}
                      >
                        {target?.name ?? "Unknown node"}
                      </button>
                      <small>
                        {target ? nodePath(target) : edge.target_node_id}
                      </small>
                    </td>
                    <td>
                      <span data-kind={edge.knowledge_kind}>
                        {edge.knowledge_kind}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
