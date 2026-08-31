import { render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useTravel } from "./useTravel";

/** Where each row is, by its label. */
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
    at({ c: 0, a: 50, b: 100 });
    view.rerender(<List rows={["c", "a", "b"]} />);
    expect(travels.map((travel) => [travel.row, travel.from, travel.to])).toEqual([
      ["c", "translateY(100px)", "translateY(0px)"],
      ["a", "translateY(-50px)", "translateY(0px)"],
      ["b", "translateY(-50px)", "translateY(0px)"],
    ]);
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
    expect(travels).toHaveLength(4);
    expect(travels.every((travel) => travel.options.composite === "add")).toBe(true);
  });

  it("animates nothing for a row it is seeing for the first time", () => {
    const { travels } = stubBrowser();
    at({ a: 0, b: 50 });
    const view = render(<List rows={["a"]} />);
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
    view.rerender(<List rows={["a", "b"]} rolling />);
    expect(frames()).toBe(1);
    at({ a: 0, b: 25 });
    tick();
    at({ a: 0, b: 0 });
    tick();
    view.rerender(<List rows={["a", "b"]} />);
    expect(travels).toEqual([]);
  });

  it("stops following once the roll is over, and asks for one loop at a time", () => {
    const { frames, tick } = stubBrowser();
    at({ a: 0, b: 50 });
    const view = render(<List rows={["a", "b"]} rolling />);
    expect(frames()).toBe(1);
    view.rerender(<List rows={["a", "b"]} rolling />);
    expect(frames()).toBe(1);
    tick();
    expect(frames()).toBe(2);
    view.rerender(<List rows={["a", "b"]} />);
    tick();
    expect(frames()).toBe(2);
  });

  it("gives up a pending frame when the list goes away mid-roll", () => {
    const { cancelled } = stubBrowser();
    at({ a: 0 });
    const quiet = render(<List rows={["a"]} />);
    quiet.unmount();
    expect(cancelled).toEqual([]);
    const rolling = render(<List rows={["a"]} rolling />);
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
