import { createBrowserRouter, type RouteObject } from "react-router";
import { NotFound } from "../pages/NotFound";
import { Welcome } from "../pages/Welcome";
import { Layout } from "./Layout";
import { RouteError } from "./RouteError";

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <Welcome /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export function createRouter() {
  return createBrowserRouter(routes);
}
