import { GitBranch, Sparkles } from "lucide-react";

export function RepositoryEmptyState() {
  function focusRepositoryInput() {
    const input = document.getElementById("repository-url");

    input?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });

    window.setTimeout(() => {
      input?.focus();
    }, 500);
  }

  return (
    <div className="repository-empty">
      <div className="repository-empty__icon" aria-hidden="true">
        <Sparkles size={24} strokeWidth={1.8} />
      </div>

      <h3 className="repository-empty__title">No atlases yet</h3>

      <p className="repository-empty__description">
        Paste a public GitHub repository URL above to generate your first
        Software Atlas. Trace will map its architecture, timeline, and design
        decisions.
      </p>

      <button
        className="repository-empty__button"
        type="button"
        onClick={focusRepositoryInput}
      >
        <GitBranch size={17} aria-hidden="true" />
        Paste a repository URL
      </button>
    </div>
  );
}
