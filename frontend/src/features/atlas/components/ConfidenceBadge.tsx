type ConfidenceBadgeProps = {
  confidence: number;
  status?: string;
};

export function ConfidenceBadge({ confidence, status }: ConfidenceBadgeProps) {
  const tier =
    confidence >= 0.8 ? "high" : confidence >= 0.6 ? "medium" : "low";
  const label = status === "candidate" ? "Candidate" : `${tier} confidence`;

  return (
    <span className="confidence-badge" data-tier={tier}>
      <span aria-hidden="true" />
      {label} · {Math.round(confidence * 100)}%
    </span>
  );
}
