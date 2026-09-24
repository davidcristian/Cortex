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

/** Render the hook over a mode the test can move, feeding its dispatches through the real reducer
 *  and the resulting link back into it. */
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
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("probes nothing while hidden, then once when the overlay opens", async () => {
    const bridge = new FakeBridge();
    const { rerender, actions } = harness(bridge);
    await flush();
    expect(bridge.linkCalls).toBe(0);

    rerender({ mode: "panel" });
    await flush();
    expect(bridge.linkCalls).toBe(1);
    expect(actions).toEqual([
      { kind: "linkProbing" },
      { kind: "linkObserved", status: { state: "ready", detail: "fake brain", notes: [] } },
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

  it("resets on hide, so the next summon asks again", async () => {
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
    const bridge = new FakeBridge();
    bridge.link = { state: "down", detail: "refused", notes: [] };
    const { view } = harness(bridge, "panel");
    await flush();
    expect(bridge.linkCalls).toBe(1);
    expect(view().state).toBe("down");

    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS);
    });
    await flush();
    expect(bridge.linkCalls).toBe(2);

    bridge.link = { state: "ready", detail: "back", notes: [] };
    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS);
    });
    await flush();
    expect(bridge.linkCalls).toBe(3);
    expect(view()).toEqual({ state: "ready", detail: "back", notes: [], probing: false });

    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS * 3);
    });
    expect(bridge.linkCalls).toBe(3);
  });

  it("re-checks a degraded link too, not only an unreachable one", async () => {
    const bridge = new FakeBridge();
    bridge.link = { state: "degraded", detail: "store down", notes: [] };
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
    bridge.link = { state: "down", detail: "refused", notes: [] };
    const { rerender } = harness(bridge, "panel");
    await flush();
    rerender({ mode: "hidden" });
    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS * 5);
    });
    expect(bridge.linkCalls).toBe(1);
  });

  it("holds the last known state when the probe itself cannot be delivered", async () => {
    const bridge = new FakeBridge();
    bridge.link = { state: "degraded", detail: "store down", notes: [] };
    const { view } = harness(bridge, "panel");
    await flush();
    expect(view().state).toBe("degraded");

    bridge.linkFails = true;
    await act(async () => {
      vi.advanceTimersByTime(LINK_RECHECK_MS);
    });
    await flush();
    expect(bridge.linkCalls).toBe(2);
    expect(view()).toEqual({ state: "degraded", detail: "store down", notes: [], probing: false });
  });

  it("keeps at most one probe outstanding across a hide and a re-summon", async () => {
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
