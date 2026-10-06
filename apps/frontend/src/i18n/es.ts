// Textos de la interfaz en español (tú, verbos simples, sin mayúsculas sostenidas).
// El material de práctica va en inglés y no vive aquí.
export const es = {
  app: {
    tagline: "Práctica de inglés B1 → B2",
    pathName: "Ruta B1 → B2 con tareas tipo TOEFL iBT (formato 2026)",
    independent: "Preparación independiente",
    trademark:
      "TOEFL y TOEFL iBT son marcas registradas de ETS. Este producto no está avalado ni aprobado por ETS.",
    skipToContent: "Saltar al contenido",
  },
  welcome: {
    title: "Practica un poco cada día",
    body: "Sesiones cortas desde tu teléfono, con corrección sobre tus propias palabras y repasos que vuelven cuando los necesitas.",
    access: "Entrar",
  },
  errors: {
    network: "No pudimos conectar. Revisa tu conexión y vuelve a intentarlo.",
    unexpected: "Algo falló de nuestro lado. Ya quedó registrado.",
    notFound: "No encontramos esto.",
    goHome: "Ir a Inicio",
    forbidden: "Esta sección es para el equipo editorial.",
    csrf: "Recarga la página para continuar.",
    rateLimited: "Espera un momento antes de intentarlo de nuevo.",
    requestId: "Código de la petición",
    sessionExpired: "Tu sesión terminó. Entra de nuevo para continuar.",
  },
  common: {
    loading: "Cargando…",
    retry: "Volver a intentar",
    offline: "Estás sin conexión. Lo que hagas se guardará cuando vuelvas a conectarte.",
  },
} as const;

export type Strings = typeof es;
