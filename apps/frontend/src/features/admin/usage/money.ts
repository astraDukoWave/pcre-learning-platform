/** Micro-USD (enteros del backend) a dólares legibles, con dos decimales o más si hace falta. */
export function usd(microusd: number): string {
  const dollars = microusd / 1_000_000;
  const digits = dollars !== 0 && Math.abs(dollars) < 0.01 ? 4 : 2;
  return `USD ${dollars.toFixed(digits)}`;
}

/** Siguiente o anterior mes `YYYY-MM`. */
export function shiftPeriod(period: string, delta: number): string {
  const [y, m] = period.split("-").map(Number) as [number, number];
  const d = new Date(Date.UTC(y, m - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

const REASONS: Record<string, string> = {
  flag_off: "apagada (flag)",
  budget_missing: "sin presupuesto configurado",
  price_missing: "sin precios configurados",
  provider_missing: "sin proveedor configurado",
};

export function reasonLabel(reason: string | null | undefined): string {
  return reason ? (REASONS[reason] ?? reason) : "encendida";
}
