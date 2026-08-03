import { render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useTravel } from "./useTravel";

/** Where each row sits, by the label it carries. jsdom has no layout, so the test IS the layout. */
const places = new Map<string, number>();

/** The travels played, in order: which row, the offset it started from, and on what terms. */
interface Travel {
  readonly row: string;
  readonly from: string;
  readonly to: string;
  readonly options: KeyframeAnimationOptions;
}

function stubBrowser() {
  const travels: Travel[] = [];
  const frames: FrameRequestCallback[] = [];
  const cancelled: number[] = [];
  vi.spyOn(HTMLElement.prototype, "offsetTop", "get").mockImplementation(function (
    this: HTMLElement,
  ) {
    return places.get(this.textContent ?? "") ?? 0;
  });
  Element.prototype.animate = function (
    this: Element,
    keyframes: Keyframe[],
    options: KeyframeAnimationOptions,
  ) {
    travels.push({
      row: this.textContent ?? "",
      from: String(keyframes[0]?.transform),
      to: String(keyframes[1]?.transform),
      options,
    });
    return { cancel: () => undefined } as unknown as Animation;
  } as typeof Element.prototype.animate;
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frames.push(callback);
    return frames.length;
  });
  vi.stubGlobal("cancelAnimationFrame", (handle: number) => cancelled.push(handle));
  return {
    travels,
    cancelled,
    /** How many frames the loop has asked for, and the browser running the newest one. */
    frames: () => frames.length,
    tick: () => frames[frames.length - 1]?.(performance.now()),
  };
}

/** Rows the test can reorder, with an optional section rolling inside the same list. */
function List({ rows, rolling = false }: { rows: readonly string[]; rolling?: boolean }) {
  const list = useRef<HTMLUListElement>(null);
  useTravel(list, ".row");
  return (
    <ul ref={list}>
      {rows.map((row) => (
        <li key={row} className="row">
          {row}
        </li>
      ))}
      {rolling ? <li data-morphing="0">rolling</li> : null}
    </ul>
  );
}

/** A caller whose list is not on screen: the ref is never attached to anything. */
function Detached() {
  const list = useRef<HTMLUListElement>(null);
  useTravel(list, ".row");
  return <ul />;
}

const at = (rows: Record<string, number>): void => {
  places.clear();
  for (const [row, place] of Object.entries(rows)) {
    places.set(row, place);
  }
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  places.clear();
});

describe("useTravel", () => {
  it("hands a moved row back the distance it moved, over the roll's own clock and curve", () => {
    const { travels } = stubBrowser();
    at({ a: 0, b: 50, c: 100 });
    const view = render(<List rows={["a", "b", "c"]} />);
    expect(travels).toEqual([]);
    // A pin regroups the list: c is lifted to the top and the two above it are pushed down. Every
    // row is where it belongs the moment the commit lands, so what is animated is the way back.
    at({ c: 0, a: 50, b: 100 });
    view.rerender(<List rows={["c", "a", "b"]} />);
    expect(travels.map((travel) => [travel.row, travel.from, travel.to])).toEqual([
      ["c", "translateY(100px)", "translateY(0px)"],
      ["a", "translateY(-50px)", "translateY(0px)"],
      ["b", "translateY(-50px)", "translateY(0px)"],
    ]);
    // The vocabulary is the roll's: same 300ms, same curve, so a row leaving and the rows moving
    // around it read as one movement rather than two.
    expect(travels[0]?.options).toEqual({
      duration: 300,
      easing: "cubic-bezier(0.4, 0, 0.2, 1)",
      composite: "add",
    });
  });

  it("composes an interrupted travel instead of cancelling it, so nothing is left stranded", () => {
    const { travels } = stubBrowser();
    at({ a: 0, b: 50 });
    const view = render(<List rows={["a", "b"]} />);
    at({ b: 0, a: 50 });
    view.rerender(<List rows={["b", "a"]} />);
    at({ a: 0, b: 50 });
    view.rerender(<List rows={["a", "b"]} />);
    // A second regrouping mid-travel finds the row visually between two places and structurally at
    // the second one. Cancelling the first animation would drop whatever of it was still in the
    // air; added, the two offsets sum to the gap the eye has and both decay to nothing.
    expect(travels).toHaveLength(4);
    expect(travels.every((travel) => travel.options.composite === "add")).toBe(true);
  });

  it("animates nothing for a row it is seeing for the first time", () => {
    const { travels } = stubBrowser();
    at({ a: 0, b: 50 });
    const view = render(<List rows={["a"]} />);
    // b arrives where it arrives: a row that was not on screen has nowhere to travel from.
    view.rerender(<List rows={["a", "b"]} />);
    expect(travels).toEqual([]);
  });

  it("animates nothing for a wobble smaller than the one the overlay animates", () => {
    const { travels } = stubBrowser();
    at({ a: 0, b: 50 });
    const view = render(<List rows={["a", "b"]} />);
    at({ a: 0, b: 51.4 });
    view.rerender(<List rows={["a", "b"]} />);
    expect(travels).toEqual([]);
  });

  it("animates nothing under prefers-reduced-motion", () => {
    const { travels } = stubBrowser();
    vi.spyOn(window, "matchMedia").mockReturnValue({
      matches: true,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    } as MediaQueryList);
    at({ a: 0, b: 50 });
    const view = render(<List rows={["a", "b"]} />);
    at({ b: 0, a: 50 });
    view.rerender(<List rows={["b", "a"]} />);
    expect(travels).toEqual([]);
  });

  it("follows a roll frame by frame, so the frame it ends is not a jump to answer", () => {
    const { travels, frames, tick } = stubBrowser();
    at({ a: 0, b: 50 });
    const view = render(<List rows={["a", "b"]} />);
    // A row starts rolling out above b. No commit happens while it rolls: the row below simply
    // travels up 50px by layout, frame by frame, and the record follows it.
    view.rerender(<List rows={["a", "b"]} rolling />);
    expect(frames()).toBe(1);
    at({ a: 0, b: 25 });
    tick();
    at({ a: 0, b: 0 });
    tick();
    // The roll ends and the row it held is dropped, which is the next commit. Measured against
    // where the record last saw b, nothing moved; measured against where the last COMMIT left it,
    // b would be answered with a 50px travel back down a distance it had already covered.
    view.rerender(<List rows={["a", "b"]} />);
    expect(travels).toEqual([]);
  });

  it("stops following once the roll is over, and asks for one loop at a time", () => {
    const { frames, tick } = stubBrowser();
    at({ a: 0, b: 50 });
    const view = render(<List rows={["a", "b"]} rolling />);
    expect(frames()).toBe(1);
    // A commit landing mid-roll finds the loop already running and leaves it alone.
    view.rerender(<List rows={["a", "b"]} rolling />);
    expect(frames()).toBe(1);
    tick(); // still rolling: another frame
    expect(frames()).toBe(2);
    view.rerender(<List rows={["a", "b"]} />);
    tick(); // the roll is gone: this is the last one
    expect(frames()).toBe(2);
  });

  it("gives up a pending frame when the list goes away mid-roll", () => {
    const { cancelled } = stubBrowser();
    at({ a: 0 });
    const quiet = render(<List rows={["a"]} />);
    quiet.unmount();
    // Nothing was following, so nothing is called off.
    expect(cancelled).toEqual([]);
    const rolling = render(<List rows={["a"]} rolling />);
    // Selecting a chat closes the switcher, which unmounts this list with a roll still running
    // inside it; the callback would go on reading a tree that is no longer on the page.
    rolling.unmount();
    expect(cancelled).toEqual([1]);
  });

  it("measures nothing when there is no list on screen to measure", () => {
    const { travels, frames } = stubBrowser();
    expect(() => render(<Detached />)).not.toThrow();
    expect(travels).toEqual([]);
    expect(frames()).toBe(0);
  });
});
