import { lazy, Suspense } from "react";
import { createBrowserRouter, type RouteObject } from "react-router";
import { ContentList } from "../features/admin/content/ContentList";
import { RevisionDetail } from "../features/admin/content/RevisionDetail";
import { PilotPage } from "../features/admin/pilot/PilotPage";
import { ReportsPage } from "../features/admin/reports/ReportsPage";
import { AdminUsers } from "../features/admin/users/AdminUsers";
import { AssessmentPage } from "../features/assessment/AssessmentPage";
import { RunPage } from "../features/assessment/RunPage";
import { RequireAuth } from "../features/auth/guards";
import { LessonPage } from "../features/lesson/LessonPage";
import { PathPage } from "../features/path/PathPage";
import { ProgressPage } from "../features/progress/ProgressPage";
import { ReviewsPage } from "../features/reviews/ReviewsPage";
import { AcceptInvite } from "../pages/AcceptInvite";
import { Home } from "../pages/Home";
import { Login } from "../pages/Login";
import { NotFound } from "../pages/NotFound";
import { Onboarding } from "../pages/Onboarding";
import { Profile } from "../pages/Profile";
import { ResetPassword } from "../pages/ResetPassword";
import { Welcome } from "../pages/Welcome";
import { Layout } from "./Layout";
import { RouteError } from "./RouteError";

// Las páginas legales cargan `react-markdown` aparte: no pesan en el bundle inicial.
const LegalPage = lazy(() => import("../pages/LegalPage").then((m) => ({ default: m.LegalPage })));
const legal = (doc: "privacidad" | "terminos" | "como-funciona") => (
  <Suspense fallback={<p>Cargando…</p>}>
    <LegalPage doc={doc} />
  </Suspense>
);

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
      { path: "privacidad", element: legal("privacidad") },
      { path: "terminos", element: legal("terminos") },
      { path: "como-funciona", element: legal("como-funciona") },
      { path: "bienvenida", element: auth(<Onboarding />) },
      { path: "inicio", element: auth(<Home />) },
      { path: "perfil", element: auth(<Profile />) },
      { path: "ruta", element: auth(<PathPage />) },
      { path: "repasos", element: auth(<ReviewsPage />) },
      { path: "progreso", element: auth(<ProgressPage />) },
      { path: "lecciones/:itemId", element: auth(<LessonPage />) },
      { path: "escenarios/:itemId", element: auth(<LessonPage kind="scenario" />) },
      { path: "comprobaciones/:formId", element: auth(<AssessmentPage />) },
      { path: "corridas/:runId", element: auth(<RunPage />) },
      { path: "admin/usuarios", element: admin(<AdminUsers />) },
      { path: "admin/contenido", element: admin(<ContentList />) },
      { path: "admin/contenido/:revisionId", element: admin(<RevisionDetail />) },
      { path: "admin/reportes", element: admin(<ReportsPage />) },
      { path: "admin/piloto", element: admin(<PilotPage />) },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export function createRouter() {
  return createBrowserRouter(routes);
}
