import { describe, expect, it } from "vitest";
import { objectiveLabel } from "./types";

describe("assessment", () => {
  it("names objectives by unit and skill", () => {
    expect(objectiveLabel("U1.R")).toBe("Unidad 1 · Lectura");
    expect(objectiveLabel("U5.W.2")).toBe("Unidad 5 · Escritura");
    expect(objectiveLabel("X")).toBe("X");
  });
});
