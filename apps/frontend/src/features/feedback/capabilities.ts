import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";

export type Capabilities = components["schemas"]["LearnerCapabilitiesOut"];

/** Qué capacidades con costo están encendidas (MVP-02). Sin ellas la interfaz ofrece la
 * alternativa gratuita; el presupuesto del alumno se comprueba al pedir (503). */
export function useCapabilities() {
  return useQuery({
    queryKey: ["capabilities"],
    queryFn: () => unwrap(api.GET("/api/v1/capabilities")),
    staleTime: 60_000,
  });
}
