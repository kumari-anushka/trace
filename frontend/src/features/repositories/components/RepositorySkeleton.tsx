export function RepositorySkeleton() {
  return (
    <article className="repository-card repository-skeleton" aria-hidden="true">
      <div className="repository-card__top">
        <span className="repository-skeleton__icon" />
        <span className="repository-skeleton__action" />
      </div>

      <div className="repository-skeleton__owner" />
      <div className="repository-skeleton__name" />

      <div className="repository-card__footer">
        <div className="repository-skeleton__date" />
        <div className="repository-skeleton__arrow" />
      </div>
    </article>
  );
}
