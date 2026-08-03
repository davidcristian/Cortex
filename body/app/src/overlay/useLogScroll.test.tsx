import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MORPH_START_EVENT } from "./morph";
import { useLogScroll } from "./useLogScroll";

// The half of the log's scroll that a roll inside it moves. Everything else this hook does (the tail
// pin, the parked position across a trip to the console) is asserted through the views that use it.

/** A log with a section that can be made to roll inside it, and nothing else. */
function Log({ rolling }: { readonly rolling: boolean }) {
  const log = useLogScroll(true);
  return (
    <div className="history" ref={log.ref} onScroll={log.onScroll}>
      {rolling ? <div className="collapse" data-morphing="76" /> : null}
    </div>
  );
}

function stage() {
  const frames: FrameRequestCallback[] = [];
  const cancelled: number[] = [];
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frames.push(callback);
    return frames.length;
  });
  vi.stubGlobal("cancelAnimationFrame", (handle: number) => cancelled.push(handle));
  return { frames: () => frames.length, cancelled };
}

/** Say a roll has started, the way `Collapse` says it: from inside the log, bubbling up to the box. */
function roll(view: { container: HTMLElement }): void {
  view.container
    .querySelector(".collapse")
    ?.dispatchEvent(new CustomEvent(MORPH_START_EVENT, { bubbles: true }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useLogScroll and a roll inside the log", () => {
  it("rides a roll that starts inside the log", () => {
    const clock = stage();
    const view = render(<Log rolling />);
    expect(clock.frames()).toBe(0);
    roll(view);
    expect(clock.frames()).toBe(1);
  });

  it("re-reads the log when a second roll starts while the first is still in the air", () => {
    const clock = stage();
    const view = render(<Log rolling />);
    roll(view);
    roll(view);
    // The first ride is called off and a new one takes its baseline from where the eye has the log
    // now, rather than from a layout that has since moved on.
    expect(clock.cancelled).toEqual([1]);
    expect(clock.frames()).toBe(2);
  });

  it("answers a start event with nothing rolling in the log by doing nothing", () => {
    // The panel's chrome rolls too, and its sections are siblings of this box rather than children
    // of it; a start event that reaches here with nothing rolling inside has nothing to follow.
    const clock = stage();
    const view = render(<Log rolling={false} />);
    view.container.querySelector(".history")?.dispatchEvent(
      new CustomEvent(MORPH_START_EVENT, { bubbles: true }),
    );
    expect(clock.frames()).toBe(0);
  });

  it("calls a running ride off when the log goes away under it", () => {
    const clock = stage();
    const view = render(<Log rolling />);
    roll(view);
    view.unmount();
    expect(clock.cancelled).toEqual([1]);
  });

  it("has nothing to call off when the log never rode anything", () => {
    const clock = stage();
    render(<Log rolling />).unmount();
    expect(clock.cancelled).toEqual([]);
  });
});
