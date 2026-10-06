import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/errors";

// Solo se reintenta lo idempotente: las lecturas, y nunca ante un 4xx.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (count, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
        return count < 2;
      },
    },
    mutations: { retry: false },
  },
});
