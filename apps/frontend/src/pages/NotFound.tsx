import { Link } from "react-router";
import { Page } from "../components/Page";
import { es } from "../i18n/es";

export function NotFound() {
  return (
    <Page title={es.errors.notFound}>
      <p>
        <Link to="/">{es.errors.goHome}</Link>
      </p>
    </Page>
  );
}
