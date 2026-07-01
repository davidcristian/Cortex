import { describe, expect, it } from "vitest";

import { initialState, isBusy, reduceError, reduceEvent, startTurn } from "./overlayState";

describe("overlayState", () => {
  it("startTurn returns a clean streaming state", () => {
    expect(startTurn()).toEqual({ ...initialState, phase: "streaming" });
  });

  it("accumulates delta text across events", () => {
    const s1 = reduceEvent(startTurn(), { kind: "delta", text: "Hel" });
    const s2 = reduceEvent(s1, { kind: "delta", text: "lo" });
    expect(s2.reply).toBe("Hello");
  });

  it("records tool activity as name: summary", () => {
    const s = reduceEvent(startTurn(), {
      kind: "toolActivity",
      toolName: "read_email",
      summary: "reading inbox",
    });
    expect(s.toolActivity).toBe("read_email: reading inbox");
  });

  it("records the latest status detail", () => {
    const s = reduceEvent(startTurn(), { kind: "status", state: "model_loading", detail: "swapping" });
    expect(s.status).toBe("swapping");
  });

  it("completes with the turn id", () => {
    const s = reduceEvent(startTurn(), { kind: "complete", turnId: "t-1" });
    expect(s.phase).toBe("complete");
    expect(s.turnId).toBe("t-1");
  });

  it("marks a brain-reported failure as code: message", () => {
    const s = reduceEvent(startTurn(), { kind: "failed", code: "overloaded", message: "busy" });
    expect(s.phase).toBe("failed");
    expect(s.error).toBe("overloaded: busy");
  });

  it("marks a transport error with its message", () => {
    const s = reduceError(startTurn(), { kind: "connection", message: "cannot reach the brain" });
    expect(s.phase).toBe("error");
    expect(s.error).toBe("cannot reach the brain");
  });

  it("is busy only while streaming", () => {
    expect(isBusy(initialState)).toBe(false);
    expect(isBusy(startTurn())).toBe(true);
  });
});
