import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("never renders raw HTML or javascript: links (AC-19)", () => {
    const { container } = render(
      <Markdown>
        {"# Título\n\n<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[clic](javascript:alert(1)) **ok**"}
      </Markdown>,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("h1")?.textContent).toBe("Título");
    expect(container.querySelector("strong")?.textContent).toBe("ok");
    const link = container.querySelector("a");
    expect(link?.getAttribute("href") ?? "").not.toContain("javascript");
  });
});
