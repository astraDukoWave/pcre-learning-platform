import ReactMarkdown, { type Components } from "react-markdown";

const components: Components = {
  a: ({ href, children }) =>
    href?.startsWith("/") ? (
      <a href={href}>{children}</a>
    ) : (
      <a href={href} rel="noreferrer noopener" target="_blank">
        {children}
      </a>
    ),
};

/** Markdown sin HTML crudo (`skipHtml`): una etiqueta escrita en el texto nunca se
 * convierte en HTML. `react-markdown` además neutraliza URLs como `javascript:` (§7). */
export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown skipHtml components={components}>
      {children}
    </ReactMarkdown>
  );
}
