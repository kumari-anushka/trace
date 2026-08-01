import { createBrowserRouter } from "react-router-dom";

import { RootLayout } from "../components/layout/RootLayout";
import { RepositoryPage } from "../pages/RepositoryPage";
import { HomePage } from "../pages/HomePage";
import { NotFoundPage } from "../pages/NotFoundPage";

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
        path: "*",
        element: <NotFoundPage />,
      },
    ],
  },
]);
