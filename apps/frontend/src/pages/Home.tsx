import { Link } from "react-router";
import { Page } from "../components/Page";
import { useMe } from "../features/auth/session";

export function Home() {
  const me = useMe();
  const name = me.data?.display_name;
  return (
    <Page title="Inicio" heading={name ? `Hola, ${name}` : "Inicio"}>
      <p>Tu práctica aparecerá aquí.</p>
      <p>
        <Link to="/perfil">Perfil</Link>
      </p>
    </Page>
  );
}
