import { lazy, Suspense } from "react";

const AskPage = lazy(async () => {
  const module = await import("../pages/AskPage");
  return { default: module.AskPage };
});

export function LazyAskPage() {
  return (
    <Suspense
      fallback={
        <main className="graph-route-loading" aria-busy="true">
          Loading Ask Atlas…
        </main>
      }
    >
      <AskPage />
    </Suspense>
  );
}
