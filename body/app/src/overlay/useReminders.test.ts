import { act, renderHook } from "@testing-library/react";
import { StrictMode } from "react";
import { describe, expect, it } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import type { DueReminder } from "../bridge/types";
import type { Action, Mode } from "./overlayState";
import { useReminders } from "./useReminders";

const reminder = (reminderId: string): DueReminder => ({
  reminderId,
  text: `remember ${reminderId}`,
  firedAtUnixMs: 1000,
  recurring: false,
  tainted: false,
  sessionId: "s1",
});

/** Flush the microtasks the bridge reads resolve on. */
async function flush(): Promise<void> {
  await act(async () => {});
}

/** Render the hook over a mode the test can move, capturing every dispatched action. */
function harness(bridge: FakeBridge, initialMode: Mode = "hidden") {
  const actions: Action[] = [];
  const dispatch = (action: Action) => {
    actions.push(action);
  };
  const rendered = renderHook(({ mode }: { mode: Mode }) => useReminders(bridge, mode, dispatch), {
    initialProps: { mode: initialMode },
  });
  return { ...rendered, actions };
}

describe("useReminders", () => {
  it("pulls nothing while the overlay is hidden, then once when it opens", async () => {
    const bridge = new FakeBridge();
    bridge.reminders = [reminder("r-1")];
    const { rerender, actions } = harness(bridge);
    await flush();
    expect(bridge.reminderListCalls).toBe(0);

    rerender({ mode: "panel" });
    await flush();
    expect(bridge.reminderListCalls).toBe(1);
    expect(actions).toEqual([{ kind: "remindersLoaded", reminders: [reminder("r-1")] }]);
  });

  it("does not refetch while the overlay stays visible, including reopening from the orb", async () => {
    const bridge = new FakeBridge();
    const { rerender } = harness(bridge, "panel");
    await flush();
    expect(bridge.reminderListCalls).toBe(1);

    for (const mode of ["orb", "preview", "panel"] as const) {
      rerender({ mode });
      await flush();
    }
    expect(bridge.reminderListCalls).toBe(1);
  });

  it("resets on hide, so the next summon pulls again", async () => {
    const bridge = new FakeBridge();
    const { rerender } = harness(bridge, "panel");
    await flush();
    rerender({ mode: "hidden" });
    await flush();
    rerender({ mode: "panel" });
    await flush();
    expect(bridge.reminderListCalls).toBe(2);
  });

  it("pulls once under StrictMode, whose mount effect fires twice", async () => {
    const bridge = new FakeBridge();
    renderHook(() => useReminders(bridge, "panel", () => undefined), { wrapper: StrictMode });
    await flush();
    expect(bridge.reminderListCalls).toBe(1);
  });

  it("leaves the previous cards in place when the pull fails", async () => {
    const bridge = new FakeBridge();
    bridge.remindersFail = true;
    const { actions } = harness(bridge, "panel");
    await flush();
    expect(bridge.reminderListCalls).toBe(1);
    expect(actions).toEqual([]);
  });

  it("dismissing drops the card first and acks over the bridge", async () => {
    const bridge = new FakeBridge();
    bridge.reminders = [reminder("r-1")];
    const { result, actions } = harness(bridge, "panel");
    await flush();

    act(() => result.current(reminder("r-1")));
    expect(actions.at(-1)).toEqual({ kind: "reminderDismissed", reminderId: "r-1" });
    await flush();
    expect(bridge.acks).toEqual([{ reminderId: "r-1", firedAtUnixMs: 1000 }]);
  });

  it("a failed ack still dismisses the card, and the next open re-surfaces it", async () => {
    const bridge = new FakeBridge();
    bridge.reminders = [reminder("r-1")];
    bridge.ackFails = true;
    const { result, rerender, actions } = harness(bridge, "panel");
    await flush();

    await act(async () => result.current(reminder("r-1")));
    expect(actions.at(-1)).toEqual({ kind: "reminderDismissed", reminderId: "r-1" });

    rerender({ mode: "hidden" });
    await flush();
    rerender({ mode: "panel" });
    await flush();
    expect(actions.at(-1)).toEqual({
      kind: "remindersLoaded",
      reminders: [reminder("r-1")],
    });
  });

});
