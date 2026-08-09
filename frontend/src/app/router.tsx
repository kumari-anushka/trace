import { createBrowserRouter } from "react-router-dom";

import { RootLayout } from "../components/layout/RootLayout";
import { HomePage } from "../pages/HomePage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RepositoryIngestionPage } from "../pages/RepositoryIngestionPage";
import { RepositoryPage } from "../pages/RepositoryPage";
import { LazyRepositoryGraphPage } from "./LazyRepositoryGraphPage";
import { LazyAtlasPage } from "./LazyAtlasPage";

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        path: "/",
        element: <HomePage />,
      },
      {
        path: "/repositories/:repositoryId",
        element: <RepositoryPage />,
      },
      {
        path: "/repositories/:repositoryId/ingestion",
        element: <RepositoryIngestionPage />,
      },
      {
        path: "/repositories/:repositoryId/graph",
        element: <LazyRepositoryGraphPage />,
      },
      {
        path: "/repositories/:repositoryId/overview",
        element: <LazyAtlasPage view="overview" />,
      },
      {
        path: "/repositories/:repositoryId/architecture",
        element: <LazyAtlasPage view="architecture" />,
      },
      {
        path: "/repositories/:repositoryId/subsystems",
        element: <LazyAtlasPage view="subsystems" />,
      },
      {
        path: "/repositories/:repositoryId/subsystems/:subsystemId",
        element: <LazyAtlasPage view="subsystems" />,
      },
      {
        path: "/repositories/:repositoryId/timeline",
        element: <LazyAtlasPage view="timeline" />,
      },
      {
        path: "*",
        element: <NotFoundPage />,
      },
    ],
  },
]);
