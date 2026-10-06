import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, setCsrfToken, unwrap } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components } from "../../api/schema";

export type Me = components["schemas"]["MeOut"];

export const ME_KEY = ["me"] as const;

/** Sesión actual: `null` si no hay (401), nunca un error para la interfaz. */
export async function fetchMe(): Promise<Me | null> {
  try {
    const me = await unwrap(api.GET("/api/v1/me"));
    setCsrfToken(me.csrf_token);
    return me;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      setCsrfToken(null);
      return null;
    }
    throw error;
  }
}

export function useMe() {
  return useQuery({ queryKey: ME_KEY, queryFn: fetchMe, staleTime: 60_000 });
}

export function useSetMe() {
  const qc = useQueryClient();
  return (me: Me | null) => {
    setCsrfToken(me ? me.csrf_token : null);
    qc.setQueryData(ME_KEY, me);
  };
}

export function homeFor(me: Me): string {
  if (!me.onboarded) return "/bienvenida";
  return "/inicio";
}

/** Solo rutas internas: evita redirecciones abiertas con `?next=`. */
export function safeNext(next: string | null): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return null;
  return next;
}
