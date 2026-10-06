import { beforeEach, describe, expect, it } from "vitest";
import { clearDraft, loadDraft, renewDraftKey, saveDraft } from "./drafts";

describe("answer drafts", () => {
  beforeEach(() => sessionStorage.clear());

  it("keeps the idempotency key while the answer is retried (EDGE-03)", () => {
    const first = saveDraft("act-1", { selected: ["a"] });
    const again = saveDraft("act-1", { selected: ["a"] });
    expect(again.key).toBe(first.key);
    expect(loadDraft("act-1")?.response).toEqual({ selected: ["a"] });
    clearDraft("act-1");
    expect(loadDraft("act-1")).toBeNull();
  });

  it("uses a new key after a 409 idempotency_conflict, keeping the new answer", () => {
    const first = saveDraft("act-2", { selected: ["a"] });
    const renewed = renewDraftKey("act-2", { selected: ["b"] });
    expect(renewed.key).not.toBe(first.key);
    expect(loadDraft("act-2")).toEqual({ response: { selected: ["b"] }, key: renewed.key });
  });
});
