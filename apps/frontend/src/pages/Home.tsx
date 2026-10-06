import { Link } from "react-router";
import { Page } from "../components/Page";
import { useMe } from "../features/auth/session";

export function Home() {
  const me = useMe();
  const name = me.data?.display_name;
  return (
    <Page title="Inicio" heading={name ? `Hola, ${name}` : "Inicio"}>
      <p>
        <Link to="/ruta">Continuar con tu ruta</Link>
      </p>
    </Page>
  );
}
