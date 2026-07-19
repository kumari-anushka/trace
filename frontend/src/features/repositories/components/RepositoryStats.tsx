const cards = [
  "Architecture",
  "Subsystems",
  "Timeline",
  "Contributors",
  "Ask AI",
  "Activity",
];

export function RepositoryStats() {
  return (
    <section className="repository-placeholder-grid">
      {cards.map((card) => (
        <article className="repository-placeholder-card" key={card}>
          <h3>{card}</h3>

          <p>Available in Week 2</p>
        </article>
      ))}
    </section>
  );
}
