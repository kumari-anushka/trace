import { ArrowUpRight, FileSearch, X } from "lucide-react";
import { useEffect } from "react";

import type { GraphEvidence } from "../../graph/graph.types";

export type EvidenceSelection = {
  title: string;
  nodeId?: string;
  edgeId?: string;
  factKind?: string;
  path?: string;
};

type EvidenceDrawerProps = {
  selection: EvidenceSelection | null;
  evidence: GraphEvidence[];
  isLoading: boolean;
  truncated: boolean;
  onClose: () => void;
};

function matches(item: GraphEvidence, selection: EvidenceSelection) {
  if (selection.nodeId && item.target_node_id === selection.nodeId) return true;
  if (selection.edgeId && item.target_edge_id === selection.edgeId) return true;
  if (
    selection.factKind === "architecture" &&
    item.provenance.component === "architecture_analysis"
  ) {
    return true;
  }
  if (
    selection.factKind &&
    item.metadata.fact_kind === selection.factKind &&
    (!selection.path ||
      item.metadata.source_path === selection.path ||
      item.excerpt?.includes(selection.path))
  ) {
    return true;
  }
  return false;
}

export function EvidenceDrawer({
  selection,
  evidence,
  isLoading,
  truncated,
  onClose,
}: EvidenceDrawerProps) {
  useEffect(() => {
    if (!selection) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose, selection]);

  if (!selection) return null;
  const matching = evidence.filter((item) => matches(item, selection));

  return (
    <div className="evidence-layer" role="presentation" onMouseDown={onClose}>
      <aside
        className="evidence-drawer"
        aria-modal="true"
        aria-labelledby="evidence-title"
        role="dialog"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p>Grounding</p>
            <h2 id="evidence-title">{selection.title}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close evidence">
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        {isLoading ? <p className="evidence-state">Loading evidence…</p> : null}
        {!isLoading && truncated ? (
          <p className="evidence-warning" role="status">
            Showing the first 500 evidence records for this snapshot.
          </p>
        ) : null}
        {!isLoading && matching.length === 0 ? (
          <div className="evidence-empty">
            <FileSearch size={22} aria-hidden="true" />
            <h3>No matching evidence</h3>
            <p>
              This item is not yet linked to evidence in the bounded snapshot.
            </p>
          </div>
        ) : null}
        <div className="evidence-list">
          {matching.map((item) => (
            <article key={item.id}>
              <div>
                <span>{item.evidence_type.replaceAll("_", " ")}</span>
                <strong>{Math.round(item.confidence * 100)}%</strong>
              </div>
              <p>{item.excerpt ?? "Persisted graph evidence"}</p>
              {item.start_line ? (
                <small>
                  Lines {item.start_line}
                  {item.end_line && item.end_line !== item.start_line
                    ? `–${item.end_line}`
                    : ""}
                </small>
              ) : null}
              {item.source_url ? (
                <a href={item.source_url} target="_blank" rel="noreferrer">
                  Open source <ArrowUpRight size={14} aria-hidden="true" />
                </a>
              ) : null}
            </article>
          ))}
        </div>
      </aside>
    </div>
  );
}
