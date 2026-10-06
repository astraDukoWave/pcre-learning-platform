import { createBrowserRouter, type RouteObject } from "react-router";
import { AdminUsers } from "../features/admin/users/AdminUsers";
import { RequireAuth } from "../features/auth/guards";
import { LessonPage } from "../features/lesson/LessonPage";
import { PathPage } from "../features/path/PathPage";
import { AcceptInvite } from "../pages/AcceptInvite";
import { Home } from "../pages/Home";
import { Login } from "../pages/Login";
import { NotFound } from "../pages/NotFound";
import { Onboarding } from "../pages/Onboarding";
import { Privacy } from "../pages/Privacy";
import { Profile } from "../pages/Profile";
import { ResetPassword } from "../pages/ResetPassword";
import { Welcome } from "../pages/Welcome";
import { Layout } from "./Layout";
import { RouteError } from "./RouteError";

const auth = (element: React.ReactNode) => <RequireAuth>{element}</RequireAuth>;
const admin = (element: React.ReactNode) => <RequireAuth admin>{element}</RequireAuth>;

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <Welcome /> },
      { path: "entrar", element: <Login /> },
      { path: "aceptar", element: <AcceptInvite /> },
      { path: "restablecer", element: <ResetPassword /> },
      { path: "privacidad", element: <Privacy /> },
      { path: "bienvenida", element: auth(<Onboarding />) },
      { path: "inicio", element: auth(<Home />) },
      { path: "perfil", element: auth(<Profile />) },
      { path: "ruta", element: auth(<PathPage />) },
      { path: "lecciones/:itemId", element: auth(<LessonPage />) },
      { path: "escenarios/:itemId", element: auth(<LessonPage kind="scenario" />) },
      { path: "admin/usuarios", element: admin(<AdminUsers />) },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export function createRouter() {
  return createBrowserRouter(routes);
}
