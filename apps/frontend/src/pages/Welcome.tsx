import { Page } from "../components/Page";
import { es } from "../i18n/es";

export function Welcome() {
  return (
    <Page title={es.welcome.title}>
      <p>{es.welcome.body}</p>
      <p>
        <strong>{es.app.pathName}</strong> · {es.app.independent}
      </p>
    </Page>
  );
}
