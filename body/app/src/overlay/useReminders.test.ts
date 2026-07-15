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

    // Mid-turn dismiss parks the panel as the orb, the reply lands as a preview, and tapping it
    // reopens the panel. The overlay never hid, so the reminders already pulled still stand.
    for (const mode of ["orb", "preview", "panel"] as const) {
      rerender({ mode });
      await flush();
    }
    expect(bridge.reminderListCalls).toBe(1);
  });

  it("re-arms on hide, so the next summon pulls again", async () => {
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
    // Production renders inside <StrictMode> (main.tsx), so the summon effect really does run
    // twice on mount. The latch is what keeps that one read, as it does for cold-start adopt.
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
    // No action at all: the reducer keeps whatever it last loaded (the chat list's rule).
    expect(actions).toEqual([]);
  });

  it("dismissing drops the card first and acks over the bridge", async () => {
    const bridge = new FakeBridge();
    bridge.reminders = [reminder("r-1")];
    const { result, actions } = harness(bridge, "panel");
    await flush();

    act(() => result.current("r-1"));
    // The dispatch is synchronous with the click; the ack is in flight behind it.
    expect(actions.at(-1)).toEqual({ kind: "reminderDismissed", reminderId: "r-1" });
    await flush();
    expect(bridge.acks).toEqual(["r-1"]);
  });

  it("a failed ack still dismisses the card, and the next open re-surfaces it", async () => {
    const bridge = new FakeBridge();
    bridge.reminders = [reminder("r-1")];
    bridge.ackFails = true;
    const { result, rerender, actions } = harness(bridge, "panel");
    await flush();

    await act(async () => result.current("r-1"));
    expect(actions.at(-1)).toEqual({ kind: "reminderDismissed", reminderId: "r-1" });

    // The brain never heard the ack, so the reminder is still deliverable on the next summon.
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
