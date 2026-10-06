import { Page } from "../components/Page";

/** Versión mínima; el texto completo llega en CS-10 (REQ-17) y es un borrador. */
export function Privacy() {
  return (
    <Page title="Aviso de privacidad">
      <p>
        <strong>Borrador pendiente de revisión.</strong> Este texto se completa antes de invitar a personas reales.
      </p>
      <p>
        Guardamos tu correo, tu meta, tus respuestas y tus resultados para que practiques y veas tu progreso. No
        vendemos tus datos. Puedes descargarlos o borrar tu cuenta desde "Perfil".
      </p>
    </Page>
  );
}
