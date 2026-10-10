import { fireEvent, render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resized } from "../test-setup";
import { MORPH_START_EVENT } from "./morph";
import { SCROLL_CLAMPED_EVENT } from "./panelParts";
import { type LogScroll, useLogScroll } from "./useLogScroll";

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
  it("follows a roll that starts inside the log", () => {
    const clock = stage();
    const view = render(<Log rolling />);
    expect(clock.frames()).toBe(0);
    roll(view, ".history .collapse");
    expect(clock.frames()).toBe(1);
  });

  it("follows a roll in the chrome, whose start event the log's own box never sees", () => {
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

  it("calls a running hold off when the log goes away under it", () => {
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

/** The chat's log alone, handing its controls out so a test can follow a reply the way it does. */
function Follower({
  onLog,
  rolling = false,
}: {
  readonly onLog: (log: LogScroll) => void;
  readonly rolling?: boolean;
}) {
  const column = useRef<HTMLDivElement>(null);
  const log = useLogScroll(true, column);
  onLog(log);
  return (
    <div ref={column}>
      {rolling ? <div className="switcher collapse" data-morphing="220" /> : null}
      <div className="history" ref={log.ref} onScroll={log.onScroll} />
    </div>
  );
}

/** Give the box an engine's geometry: a box 100px tall whose scroll position is clamped to its
 *  content, as a browser clamps it. */
function follower(rolling = false) {
  let log!: LogScroll;
  const view = render(<Follower onLog={(next) => (log = next)} rolling={rolling} />);
  const el = view.container.querySelector(".history") as HTMLDivElement;
  const content = { height: 500 };
  const box = { height: 100 };
  let top = 0;
  Object.defineProperty(el, "scrollHeight", { configurable: true, get: () => content.height });
  Object.defineProperty(el, "clientHeight", { configurable: true, get: () => box.height });
  Object.defineProperty(el, "scrollTop", {
    configurable: true,
    get: () => top,
    set: (value: number) => {
      top = Math.max(0, Math.min(value, content.height - box.height));
    },
  });
  return { log, el, content, box, view };
}

describe("useLogScroll and the scroll events nobody made", () => {
  it("keeps following when content grows under a box that did not move", () => {
    const { log, el, content } = follower();
    log.toTail();
    expect(el.scrollTop).toBe(400);
    content.height = 1045;
    fireEvent.scroll(el);
    log.toTail();
    expect(el.scrollTop).toBe(945);
  });

  it("stops following once the reader moves away from the end, however the content grows", () => {
    const { log, el, content } = follower();
    log.toTail();
    el.scrollTop = 100;
    fireEvent.scroll(el);
    content.height = 900;
    fireEvent.scroll(el);
    log.toTail();
    expect(el.scrollTop).toBe(100);
  });

  it("keeps following from the place a reader scrolled back to at the end", () => {
    const { log, el, content } = follower();
    log.toTail();
    el.scrollTop = 100;
    fireEvent.scroll(el);
    el.scrollTop = 395;
    fireEvent.scroll(el);
    content.height = 1045;
    fireEvent.scroll(el);
    log.toTail();
    expect(el.scrollTop).toBe(945);
  });
});

describe("useLogScroll and the panel measuring itself", () => {
  /** The panel grows: measured at its new height the box's range is shorter, so the engine clamps
   *  the position, and the move starts from the old height with the box still there. */
  function grow(el: HTMLDivElement, box: { height: number }): void {
    box.height = 300;
    el.scrollTop = el.scrollTop;
    el.dispatchEvent(new Event(SCROLL_CLAMPED_EVENT));
    box.height = 150;
    fireEvent.scroll(el);
  }

  it("keeps following through a position the panel's measurement clamped", () => {
    const { log, el, box } = follower();
    log.toTail();
    grow(el, box);
    expect(el.scrollTop).toBe(200);
    resized(el);
    expect(el.scrollTop).toBe(350);
  });

  it("still stops following when the reader scrolls after the clamp", () => {
    const { log, el, box } = follower();
    log.toTail();
    grow(el, box);
    el.scrollTop = 50;
    fireEvent.scroll(el);
    resized(el);
    expect(el.scrollTop).toBe(50);
  });
});

describe("useLogScroll and a box that changes size under the reader", () => {
  it("follows to the end when the panel makes the box shorter with no scroll event", () => {
    const { log, el, box } = follower();
    log.toTail();
    box.height = 13;
    expect(resized(el)).toBe(1);
    expect(el.scrollTop).toBe(487);
  });

  it("leaves a reader who scrolled up where they are", () => {
    const { log, el, box } = follower();
    log.toTail();
    el.scrollTop = 100;
    fireEvent.scroll(el);
    box.height = 13;
    resized(el);
    expect(el.scrollTop).toBe(100);
  });

  it("leaves the box to a roll running in its column, and follows once the roll is over", () => {
    const { log, el, box, view } = follower(true);
    log.toTail();
    box.height = 13;
    resized(el);
    expect(el.scrollTop).toBe(400);
    view.container.querySelector(".switcher")?.removeAttribute("data-morphing");
    resized(el);
    expect(el.scrollTop).toBe(487);
  });

  it("follows with no column to look for a roll in, and stops watching when the log goes", () => {
    const view = render(<Orphan />);
    const el = view.container.querySelector(".history") as HTMLDivElement;
    Object.defineProperty(el, "scrollHeight", { configurable: true, value: 300 });
    resized(el);
    expect(el.scrollTop).toBe(300);
    view.unmount();
    expect(resized(el)).toBe(0);
  });
});
