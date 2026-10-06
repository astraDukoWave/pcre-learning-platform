import { ApiError } from "../api/errors";
import { es } from "../i18n/es";
import { Notice } from "./Notice";

/** Un error dice qué pasó y qué hacer, con el `request_id` si lo hay. */
export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  if (error instanceof ApiError) {
    return (
      <Notice tone="system-error" requestId={error.status >= 500 ? error.requestId : null}>
        {error.message}
      </Notice>
    );
  }
  return <Notice tone="system-error">{es.errors.unexpected}</Notice>;
}
