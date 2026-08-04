import { lazy, Suspense } from "react";

const RepositoryGraphPage = lazy(async () => {
  const module = await import("../pages/RepositoryGraphPage");
  return { default: module.RepositoryGraphPage };
});

export function LazyRepositoryGraphPage() {
  return (
    <Suspense
      fallback={
        <main className="graph-route-loading" aria-busy="true">
          Loading graph explorer…
        </main>
      }
    >
      <RepositoryGraphPage />
    </Suspense>
  );
}
