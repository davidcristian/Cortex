import { describe, expect, it, vi } from "vitest";

import { FakeBridge } from "./fakeBridge";

describe("FakeBridge", () => {
  it("records the call and forwards events + errors to the sink", () => {
    const bridge = new FakeBridge();
    const onEvent = vi.fn();
    const onError = vi.fn();
    bridge.converse("s1", "hi", { onEvent, onError });
    expect(bridge.calls).toEqual([{ sessionId: "s1", text: "hi" }]);
    bridge.emit({ kind: "delta", text: "x" });
    bridge.fail({ kind: "rpc", message: "boom" });
    expect(onEvent).toHaveBeenCalledWith({ kind: "delta", text: "x" });
    expect(onError).toHaveBeenCalledWith({ kind: "rpc", message: "boom" });
  });

  it("emit and fail are no-ops with no active turn (before converse, and after cancel)", () => {
    const bridge = new FakeBridge();
    expect(() => {
      bridge.emit({ kind: "delta", text: "x" });
      bridge.fail({ kind: "rpc", message: "b" });
    }).not.toThrow();
    const cancel = bridge.converse("s", "t", { onEvent: vi.fn(), onError: vi.fn() });
    cancel();
    expect(() => bridge.emit({ kind: "delta", text: "y" })).not.toThrow();
  });

  it("records confirm answers in order and resolves", async () => {
    const bridge = new FakeBridge();
    await bridge.respondConfirm("c-1", true);
    await bridge.respondConfirm("c-2", false);
    expect(bridge.confirms).toEqual([
      { confirmId: "c-1", approved: true },
      { confirmId: "c-2", approved: false },
    ]);
  });

  it("rejects a confirm answer when the failure flag is set, still recording the attempt", async () => {
    const bridge = new FakeBridge();
    bridge.confirmFails = true;
    await expect(bridge.respondConfirm("c-1", true)).rejects.toThrow("confirm failed");
    expect(bridge.confirms).toEqual([{ confirmId: "c-1", approved: true }]);
  });
});
