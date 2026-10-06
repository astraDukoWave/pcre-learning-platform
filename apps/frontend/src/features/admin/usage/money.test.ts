import { describe, expect, it } from "vitest";
import { reasonLabel, shiftPeriod, usd } from "./money";

describe("usage formatting", () => {
  it("formats micro-USD as dollars", () => {
    expect(usd(25_000_000)).toBe("USD 25.00");
    expect(usd(4_300)).toBe("USD 0.0043");
    expect(usd(0)).toBe("USD 0.00");
  });

  it("moves between calendar months across years", () => {
    expect(shiftPeriod("2026-12", 1)).toBe("2027-01");
    expect(shiftPeriod("2026-01", -1)).toBe("2025-12");
  });

  it("explains why a capability is off", () => {
    expect(reasonLabel("budget_missing")).toBe("sin presupuesto configurado");
    expect(reasonLabel(null)).toBe("encendida");
  });
});
