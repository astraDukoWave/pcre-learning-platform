import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../api/client";
import { Markdown } from "../components/Markdown";
import { Page } from "../components/Page";
import comoFunciona from "../legal/como-funciona.md?raw";
import privacidad from "../legal/privacidad.md?raw";
import terminos from "../legal/terminos.md?raw";

const DOCS = {
  privacidad: { title: "Aviso de privacidad", text: privacidad },
  terminos: { title: "Términos de uso", text: terminos },
  "como-funciona": { title: "Cómo funciona", text: comoFunciona },
} as const;

export type LegalDoc = keyof typeof DOCS;

/** Páginas legales y de ayuda (REQ-17). Los textos viven en `src/legal/*.md`; el contacto
 * de privacidad sale de la configuración del servidor (`PRIVACY_CONTACT_EMAIL`). */
export function LegalPage({ doc }: { doc: LegalDoc }) {
  const legal = useQuery({
    queryKey: ["legal"],
    queryFn: () => unwrap(api.GET("/api/v1/legal")),
    staleTime: Infinity,
  });
  const { title, text } = DOCS[doc];
  const contact = legal.data?.privacy_contact_email ?? "el contacto de privacidad";
  const body = text.replace(/^# .*\n/, "").replaceAll("{{PRIVACY_CONTACT_EMAIL}}", contact);
  return (
    <Page title={title}>
      <Markdown>{body}</Markdown>
    </Page>
  );
}
