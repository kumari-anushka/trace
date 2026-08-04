import cytoscape, {
  type Core,
  type EventObjectNode,
  type StylesheetStyle,
} from "cytoscape";
import { LocateFixed, Minus, Plus, RefreshCw } from "lucide-react";
import { useEffect, useRef } from "react";

import type { GraphEdge, GraphMetric, GraphNode } from "../graph.types";

type GraphCanvasProps = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metrics: GraphMetric[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
};

const graphStyles: StylesheetStyle[] = [
  {
    selector: "node",
    style: {
      "background-color": "#466a91",
      "border-color": "#8cbfff",
      "border-width": 1,
      color: "#dfe9f5",
      label: "data(label)",
      "font-family": "Inter, ui-sans-serif, system-ui",
      "font-size": 8,
      "min-zoomed-font-size": 8,
      "text-background-color": "#090d14",
      "text-background-opacity": 0.78,
      "text-background-padding": "3px",
      "text-margin-y": 8,
      "text-valign": "bottom",
      "text-wrap": "ellipsis",
      "text-max-width": "100px",
      height: "data(size)",
      width: "data(size)",
    },
  },
  {
    selector: 'node[type = "repository_snapshot"]',
    style: {
      "background-color": "#5b9cff",
      "border-color": "#b9d6ff",
      shape: "diamond",
    },
  },
  {
    selector: 'node[type = "directory"]',
    style: {
      "background-color": "#7859b6",
      "border-color": "#bca6ec",
      shape: "round-rectangle",
    },
  },
  {
    selector: 'node[type = "file"]',
    style: {
      "background-color": "#287f88",
      "border-color": "#72d5d7",
      shape: "round-rectangle",
    },
  },
  {
    selector: 'node[type = "external_dependency"]',
    style: {
      "background-color": "#a66a30",
      "border-color": "#f0b26e",
      shape: "hexagon",
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-color": "#ffffff",
      "border-width": 3,
      "overlay-color": "#5b9cff",
      "overlay-opacity": 0.12,
      "overlay-padding": 8,
    },
  },
  {
    selector: "edge",
    style: {
      "curve-style": "bezier",
      "line-color": "#526174",
      opacity: 0.64,
      width: 1.2,
    },
  },
  {
    selector: 'edge[relationship = "IMPORTS"]',
    style: {
      "line-color": "#5b9cff",
      "target-arrow-color": "#5b9cff",
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.7,
      opacity: 0.8,
    },
  },
  {
    selector: 'edge[kind = "derived"]',
    style: { "line-style": "dashed" },
  },
  {
    selector: 'edge[kind = "inferred"]',
    style: { "line-style": "dotted", opacity: 0.48 },
  },
];

export function GraphCanvas({
  nodes,
  edges,
  metrics,
  selectedNodeId,
  onSelectNode,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cytoscapeRef = useRef<Core | null>(null);
  const onSelectNodeRef = useRef(onSelectNode);

  useEffect(() => {
    onSelectNodeRef.current = onSelectNode;
  }, [onSelectNode]);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const centralityByNode = new Map(
      metrics
        .filter((metric) => metric.metric_name === "degree_centrality")
        .map((metric) => [metric.node_id, metric.value]),
    );
    const instance = cytoscape({
      container: containerRef.current,
      elements: [
        ...nodes.map((node) => ({
          data: {
            id: node.id,
            label: node.name,
            type: node.entity_type,
            kind: node.knowledge_kind,
            size: 23 + Math.min(17, (centralityByNode.get(node.id) ?? 0) * 48),
          },
        })),
        ...edges.map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source_node_id,
            target: edge.target_node_id,
            relationship: edge.relationship_type,
            kind: edge.knowledge_kind,
          },
        })),
      ],
      style: graphStyles,
      layout: {
        name: "cose",
        animate: false,
        componentSpacing: 54,
        idealEdgeLength: 72,
        nodeRepulsion: () => 5200,
        randomize: true,
      },
      minZoom: 0.25,
      maxZoom: 2.5,
      wheelSensitivity: 0.18,
    });

    const selectNode = (event: EventObjectNode) => {
      onSelectNodeRef.current(event.target.id());
    };
    instance.on("tap", "node", selectNode);
    cytoscapeRef.current = instance;

    return () => {
      instance.removeListener("tap", "node", selectNode);
      instance.destroy();
      cytoscapeRef.current = null;
    };
  }, [edges, metrics, nodes]);

  useEffect(() => {
    const instance = cytoscapeRef.current;
    if (!instance) {
      return;
    }

    instance.nodes().unselect();
    if (!selectedNodeId) {
      return;
    }

    const selected = instance.getElementById(selectedNodeId);
    if (selected.nonempty()) {
      selected.select();
      instance.animate({ center: { eles: selected }, duration: 220 });
    }
  }, [selectedNodeId]);

  function fitGraph() {
    const instance = cytoscapeRef.current;
    if (!instance) {
      return;
    }
    instance.animate({
      fit: { eles: instance.elements(), padding: 34 },
      duration: 220,
    });
  }

  function relayoutGraph() {
    cytoscapeRef.current
      ?.layout({
        name: "cose",
        animate: true,
        animationDuration: 360,
        componentSpacing: 54,
        idealEdgeLength: 72,
        randomize: true,
      })
      .run();
  }

  function changeZoom(delta: number) {
    const instance = cytoscapeRef.current;
    if (!instance) {
      return;
    }
    instance.zoom({
      level: Math.max(
        instance.minZoom(),
        Math.min(instance.maxZoom(), instance.zoom() + delta),
      ),
      renderedPosition: {
        x: instance.width() / 2,
        y: instance.height() / 2,
      },
    });
  }

  return (
    <div className="graph-canvas-shell">
      <div className="graph-canvas-toolbar" aria-label="Graph canvas controls">
        <button
          type="button"
          onClick={() => changeZoom(0.18)}
          aria-label="Zoom in"
        >
          <Plus size={15} aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={() => changeZoom(-0.18)}
          aria-label="Zoom out"
        >
          <Minus size={15} aria-hidden="true" />
        </button>
        <button type="button" onClick={fitGraph} aria-label="Fit graph to view">
          <LocateFixed size={15} aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={relayoutGraph}
          aria-label="Re-layout graph"
        >
          <RefreshCw size={14} aria-hidden="true" />
        </button>
      </div>
      <div
        className="graph-canvas"
        ref={containerRef}
        aria-hidden="true"
        data-node-count={nodes.length}
        data-edge-count={edges.length}
      />
    </div>
  );
}
