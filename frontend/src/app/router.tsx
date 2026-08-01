import { createBrowserRouter } from "react-router-dom";

import { RootLayout } from "../components/layout/RootLayout";
import { HomePage } from "../pages/HomePage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RepositoryIngestionPage } from "../pages/RepositoryIngestionPage";
import { RepositoryPage } from "../pages/RepositoryPage";

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
        path: "*",
        element: <NotFoundPage />,
      },
    ],
  },
]);
