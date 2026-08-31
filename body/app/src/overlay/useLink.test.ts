import { act, renderHook } from "@testing-library/react";
import { StrictMode, useCallback, useReducer } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import { INITIAL_LINK, type LinkView } from "./linkState";
import { type Action, type Mode, createInitialState, reduce } from "./overlayState";
import { LINK_RECHECK_MS, useLink } from "./useLink";

/** Flush the microtasks the probe resolves on. */
async function flush(): Promise<void> {
  await act(async () => {});
}

/**
 * Render the hook over a mode the test can move, feeding its dispatches through the real
 * reducer and the resulting link back into it. That closes the real loop: the recovery cadence
 * is driven by the state the hook's own answers produce, so a mis-folded answer would show up
 * here as a wrong number of probes rather than passing on a hand-written stub.
 */
function harness(bridge: FakeBridge, initialMode: Mode = "hidden") {
  const actions: Action[] = [];
  const seen = { link: INITIAL_LINK as LinkView };
  const rendered = renderHook(
    ({ mode }: { mode: Mode }) => {
      const [state, apply] = useReducer(reduce, undefined, () => createInitialState("s1"));
      const dispatch = useCallback(
        (action: Action) => {
          actions.push(action);
          apply(action);
        },
        [apply],
      );
      seen.link = state.link;
      useLink(bridge, mode, state.link, dispatch);
    },
    { initialProps: { mode: initialMode } },
  );
  return { ...rendered, actions, view: () => seen.link };
}

describe("useLink", () => {
  beforeEach(() => {
    // Plain fake timers: the recovery cadence is the thing under test, and every probe here
    // resolves on a microtask, so nothing needs the clock to move on its own.
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("probes nothing while hidden, then once when the overlay opens", async () => {
    // Nothing is on screen for the dot to report, and the body is resident for days.
    const bridge = new FakeBridge();
    const { rerender, actions } = harness(bridge);
    await flush();
    expect(bridge.linkCalls).toBe(0);

    rerender({ mode: "panel" });
    await flush();
    expect(bridge.linkCalls).toBe(1);
    expect(actions).toEqual([
      { kind: "linkProbing" },
      { kind: "linkObserved", status: { state: "ready", detail: "fake brain" } },
    ]);
  });

  it("does not re-probe while the overlay stays visible in another shape", async () => {
    const bridge = new FakeBridge();
    const { rerender } = harness(bridge, "panel");
    await flush();
    for (const mode of ["orb", "preview", "panel"] as const) {
      rerender({ mode });
      await flush();
    }
    expect(bridge.linkCalls).toBe(1);
  });

  it("re-arms on hide, so the next summon asks again", async () => {
    const bridge = new FakeBridge();
    const { rerender } = harness(bridge, "panel");
    await flush();
    rerender({ mode: "hidden" });
    await flush();
    rerender({ mode: "panel" });
    await flush();
    expect(bridge.linkCalls).toBe(2);
  });

  it("probes once under StrictMode, whose mount effect fires twice", async () => {
    const bridge = new FakeBridge();
    renderHook(() => useLink(bridge, "panel", INITIAL_LINK, () => undefined), {
      wrapper: StrictMode,
    });
    await flush();
    expect(bridge.linkCalls).toBe(1);
  });

  it("costs nothing while a ready link is on screen", async () => {
    // The steady state of a working system: one probe on summon, then silence. A liveness
    // poll would spend a request here every few seconds, forever.
    const bridge = new FakeBridge();
    harness(bridge, "panel");
    await flush();
    expect(bridge.linkCalls).toBe(1);

    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS * 4);
    });
    expect(bridge.linkCalls).toBe(1);
  });

  it("keeps re-checking an unhealthy link until it answers ready", async () => {
    // The red dot has to be able to go green on its own: nothing streams while the panel sits
    // open, and dismissing to re-summon is not a recovery mechanism.
    const bridge = new FakeBridge();
    bridge.link = { state: "down", detail: "refused" };
    const { view } = harness(bridge, "panel");
    await flush();
    expect(bridge.linkCalls).toBe(1);
    expect(view().state).toBe("down");

    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS);
    });
    await flush();
    expect(bridge.linkCalls).toBe(2);

    bridge.link = { state: "ready", detail: "back" };
    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS);
    });
    await flush();
    expect(bridge.linkCalls).toBe(3);
    expect(view()).toEqual({ state: "ready", detail: "back", probing: false });

    // Recovered, so the cadence stops of its own accord.
    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS * 3);
    });
    expect(bridge.linkCalls).toBe(3);
  });

  it("re-checks a degraded link too, not only an unreachable one", async () => {
    const bridge = new FakeBridge();
    bridge.link = { state: "degraded", detail: "store down" };
    harness(bridge, "panel");
    await flush();
    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS);
    });
    await flush();
    expect(bridge.linkCalls).toBe(2);
  });

  it("stops re-checking as soon as the overlay hides", async () => {
    const bridge = new FakeBridge();
    bridge.link = { state: "down", detail: "refused" };
    const { rerender } = harness(bridge, "panel");
    await flush();
    rerender({ mode: "hidden" });
    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS * 5);
    });
    expect(bridge.linkCalls).toBe(1);
  });

  it("holds the last known state when the probe itself cannot be delivered", async () => {
    // The command answers a state even for a dead brain, so a rejection is the body's own
    // plumbing failing. That is not evidence about the brain, and must not overwrite evidence.
    const bridge = new FakeBridge();
    bridge.link = { state: "degraded", detail: "store down" };
    const { view } = harness(bridge, "panel");
    await flush();
    expect(view().state).toBe("degraded");

    bridge.linkFails = true;
    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS);
    });
    await flush();
    expect(bridge.linkCalls).toBe(2);
    // What was last proven still stands, and the view is not stuck mid-probe.
    expect(view()).toEqual({ state: "degraded", detail: "store down", probing: false });
  });

  it("keeps at most one probe outstanding across a hide and a re-summon", async () => {
    // A hanging probe plus a fast dismiss/summon would otherwise leave two answers racing,
    // and the loser could overwrite the newer state.
    const bridge = new FakeBridge();
    bridge.linkHangs = true;
    const { rerender, view } = harness(bridge, "panel");
    await flush();
    expect(bridge.linkCalls).toBe(1);

    rerender({ mode: "hidden" });
    await flush();
    rerender({ mode: "panel" });
    await flush();
    expect(bridge.linkCalls).toBe(1);
    expect(view().probing).toBe(true);
  });
});
