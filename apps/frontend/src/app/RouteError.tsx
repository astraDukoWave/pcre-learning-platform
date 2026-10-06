import { Link, useRouteError } from "react-router";
import { ApiError } from "../api/errors";
import { Notice } from "../components/Notice";
import { Page } from "../components/Page";
import { es } from "../i18n/es";

export function RouteError() {
  const error = useRouteError();
  const requestId = error instanceof ApiError ? error.requestId : null;
  return (
    <Page title={es.errors.unexpected}>
      <Notice tone="system-error" requestId={requestId}>
        {error instanceof ApiError ? error.message : es.errors.unexpected}
      </Notice>
      <Link to="/">{es.errors.goHome}</Link>
    </Page>
  );
}
