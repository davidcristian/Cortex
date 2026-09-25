import { describe, expect, it, vi } from "vitest";

import { FakeBridge } from "./fakeBridge";
import type { AttachedImage, DueReminder } from "./types";

const PICTURE: AttachedImage = {
  data: new Uint8Array([0x89, 0x50]),
  mimeType: "image/png",
  width: 1600,
  height: 900,
};

const reminder = (reminderId: string): DueReminder => ({
  reminderId,
  text: `remember ${reminderId}`,
  firedAtUnixMs: 1000,
  recurring: false,
  tainted: false,
  sessionId: "s1",
});

describe("FakeBridge", () => {
  it("records the call and forwards events + errors to the sink", () => {
    const bridge = new FakeBridge();
    const onEvent = vi.fn();
    const onError = vi.fn();
    bridge.converse("s1", "hi", [PICTURE], { onEvent, onError });
    expect(bridge.calls).toEqual([{ sessionId: "s1", text: "hi" }]);
    expect(bridge.attached).toEqual([[PICTURE]]);
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
    const cancel = bridge.converse("s", "t", [], { onEvent: vi.fn(), onError: vi.fn() });
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

  it("serves the due reminders it was given and counts the pulls", async () => {
    const bridge = new FakeBridge();
    bridge.reminders = [reminder("r-1")];
    expect(await bridge.listDueReminders()).toEqual([reminder("r-1")]);
    await bridge.listDueReminders();
    expect(bridge.reminderListCalls).toBe(2);
  });

  it("acks a held fire true and an unknown id or replaced fire false, recording each", async () => {
    const bridge = new FakeBridge();
    bridge.reminders = [reminder("r-1")];
    expect(await bridge.ackReminder("r-1", 1000)).toBe(true);
    expect(await bridge.ackReminder("gone", 1000)).toBe(false);
    expect(await bridge.ackReminder("r-1", 999)).toBe(false);
    expect(bridge.acks).toEqual([
      { reminderId: "r-1", firedAtUnixMs: 1000 },
      { reminderId: "gone", firedAtUnixMs: 1000 },
      { reminderId: "r-1", firedAtUnixMs: 999 },
    ]);
  });

  it("answers a link status by default, counting the probes", async () => {
    const bridge = new FakeBridge();
    expect(await bridge.checkLink()).toEqual({ state: "ready", detail: "fake brain", notes: [] });
    bridge.link = { state: "down", detail: "refused", notes: [] };
    expect(await bridge.checkLink()).toEqual({ state: "down", detail: "refused", notes: [] });
    expect(bridge.linkCalls).toBe(2);
  });

  it("rejects a probe when the flag is set, and hangs one when asked to", async () => {
    const bridge = new FakeBridge();
    bridge.linkFails = true;
    await expect(bridge.checkLink()).rejects.toThrow("probe failed");

    bridge.linkHangs = true;
    let settled = false;
    void bridge.checkLink().then(() => {
      settled = true;
    });
    await Promise.resolve();
    expect(settled).toBe(false);
    // `linkHangs` is checked before `linkFails`, so setting both gives a probe that never settles.
    expect(bridge.linkCalls).toBe(2);
  });

  it("rejects the reminder calls when their failure flags are set", async () => {
    const bridge = new FakeBridge();
    bridge.remindersFail = true;
    bridge.ackFails = true;
    await expect(bridge.listDueReminders()).rejects.toThrow("reminders failed");
    await expect(bridge.ackReminder("r-1", 1000)).rejects.toThrow("ack failed");
    expect(bridge.reminderListCalls).toBe(1);
    expect(bridge.acks).toEqual([{ reminderId: "r-1", firedAtUnixMs: 1000 }]);
  });
});

describe("FakeBridge preferences", () => {
  it("counts reads, records writes, and can be set to fail on either call", async () => {
    const bridge = new FakeBridge();
    bridge.preferences = [{ key: "overlay.mark", value: "tangent" }];
    expect(await bridge.getPreferences()).toEqual([{ key: "overlay.mark", value: "tangent" }]);
    expect(bridge.preferenceReads).toBe(1);
    await bridge.setPreference("overlay.theme", "midnight");
    expect(bridge.preferenceWrites).toEqual([{ key: "overlay.theme", value: "midnight" }]);

    bridge.preferencesFail = true;
    await expect(bridge.getPreferences()).rejects.toThrow("preferences failed");
    bridge.preferenceWriteFails = true;
    await expect(bridge.setPreference("overlay.mark", "hunch")).rejects.toThrow(
      "preference write failed",
    );
  });
});
