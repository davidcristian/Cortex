import { render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MORPH_START_EVENT } from "./morph";
import { useLogScroll } from "./useLogScroll";

/** The panel's chat column: the chrome that rolls, the log, and a section that rolls inside it. */
function Log({
  rolling = false,
  chrome = false,
  loose = false,
}: {
  readonly rolling?: boolean;
  readonly chrome?: boolean;
  readonly loose?: boolean;
}) {
  const column = useRef<HTMLDivElement>(null);
  const log = useLogScroll(true, column);
  return (
    <div className="stage">
      <div className="view" ref={column}>
        {chrome ? <div className="switcher collapse" data-morphing="220" /> : null}
        <div className="history" ref={log.ref} onScroll={log.onScroll}>
          {rolling ? <div className="collapse" data-morphing="76" /> : null}
        </div>
      </div>
      {/* Another column of the same panel, in place of the console: it rolls too, and its rolls
          are not this log's business. */}
      {loose ? <div className="pane collapse" data-morphing="120" /> : null}
    </div>
  );
}

/** The same view with no column to listen on, which is every render before the panel commits. */
function Orphan() {
  const column = useRef<HTMLDivElement>(null);
  const log = useLogScroll(true, column);
  return <div className="history" ref={log.ref} onScroll={log.onScroll} />;
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

/** Say a roll has started, the way `Collapse` says it: from the section itself, bubbling. */
function roll(view: { container: HTMLElement }, selector: string): void {
  view.container
    .querySelector(selector)
    ?.dispatchEvent(new CustomEvent(MORPH_START_EVENT, { bubbles: true }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useLogScroll and the rolls it hears", () => {
  it("rides a roll that starts inside the log", () => {
    const clock = stage();
    const view = render(<Log rolling />);
    expect(clock.frames()).toBe(0);
    roll(view, ".history .collapse");
    expect(clock.frames()).toBe(1);
  });

  it("rides a roll in the chrome, whose start event the log's own box never sees", () => {
    const clock = stage();
    const view = render(<Log chrome />);
    const box = view.container.querySelector(".history") as HTMLDivElement;
    const heard: string[] = [];
    box.addEventListener(MORPH_START_EVENT, () => heard.push("box"));
    roll(view, ".switcher");
    expect(heard).toEqual([]);
    expect(clock.frames()).toBe(1);
  });

  it("leaves a roll in another column of the panel alone", () => {
    const clock = stage();
    const view = render(<Log loose />);
    roll(view, ".pane");
    expect(clock.frames()).toBe(0);
  });

  it("re-reads the log when a second roll starts while the first is still in the air", () => {
    const clock = stage();
    const view = render(<Log rolling chrome />);
    roll(view, ".history .collapse");
    roll(view, ".switcher");
    expect(clock.cancelled).toEqual([1]);
    expect(clock.frames()).toBe(2);
  });

  it("listens to nothing while the column it was handed is unmounted", () => {
    const clock = stage();
    const view = render(<Orphan />);
    view.container
      .querySelector(".history")
      ?.dispatchEvent(new CustomEvent(MORPH_START_EVENT, { bubbles: true }));
    expect(clock.frames()).toBe(0);
    expect(() => view.unmount()).not.toThrow();
  });

  it("calls a running ride off when the log goes away under it", () => {
    const clock = stage();
    const view = render(<Log rolling />);
    roll(view, ".history .collapse");
    view.unmount();
    expect(clock.cancelled).toEqual([1]);
  });

  it("has nothing to call off when the log never rode anything", () => {
    const clock = stage();
    render(<Log rolling />).unmount();
    expect(clock.cancelled).toEqual([]);
  });
});
