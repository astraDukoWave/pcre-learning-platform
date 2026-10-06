import { Link, Navigate, useSearchParams } from "react-router";
import { Notice } from "../components/Notice";
import { Page } from "../components/Page";
import { homeFor, useMe } from "../features/auth/session";
import { es } from "../i18n/es";

export function Welcome() {
  const me = useMe();
  const [params] = useSearchParams();
  if (me.data) return <Navigate to={homeFor(me.data)} replace />;
  return (
    <Page title={es.welcome.title}>
      {params.get("cuenta") === "borrada" ? <Notice tone="success">Tu cuenta y tus datos se borraron.</Notice> : null}
      <p>{es.welcome.body}</p>
      <p>
        <strong>{es.app.pathName}</strong> · {es.app.independent}
      </p>
      <p>
        <Link to="/entrar">{es.welcome.access}</Link>
      </p>
    </Page>
  );
}
