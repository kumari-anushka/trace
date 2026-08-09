import { lazy, Suspense } from "react";

import type { AtlasView } from "../pages/AtlasPage";

const AtlasPage = lazy(async () => {
  const module = await import("../pages/AtlasPage");
  return { default: module.AtlasPage };
});

export function LazyAtlasPage({ view }: { view: AtlasView }) {
  return (
    <Suspense
      fallback={
        <main className="graph-route-loading" aria-busy="true">
          Loading Software Atlas…
        </main>
      }
    >
      <AtlasPage view={view} />
    </Suspense>
  );
}
