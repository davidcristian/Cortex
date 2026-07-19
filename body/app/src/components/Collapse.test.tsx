import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Collapse } from "./Collapse";

const HEIGHT = 120;

interface Roll {
  readonly from: number;
  readonly to: number;
  readonly fade: readonly [number, number];
}

/**
 * jsdom has neither the Web Animations API nor layout, so both are stood in for. The fake is
 * faithful in the way that matters: a running animation OVERRIDES the measured height, so a roll
 * interrupted half way can be read for where it had got to.
 */
function stubBrowser() {
  const rolls: Roll[] = [];
  const finishers: (() => void)[] = [];
  const box = { natural: HEIGHT, displayed: 0 };
  let running = false;
  let playState: AnimationPlayState = "running";

  Element.prototype.getBoundingClientRect = (() =>
    ({ height: running ? box.displayed : box.natural }) as DOMRect) as () => DOMRect;

  Element.prototype.animate = ((keyframes: Keyframe[]) => {
    const read = (frame: Keyframe | undefined) => ({
      height: Number.parseFloat(String(frame?.height ?? "0")),
      opacity: Number(frame?.opacity ?? 0),
    });
    const from = read(keyframes[0]);
    const to = read(keyframes[1]);
    rolls.push({ from: from.height, to: to.height, fade: [from.opacity, to.opacity] });
    running = true;
    const animation = {
      get playState() {
        return playState;
      },
      onfinish: null as (() => void) | null,
      cancel: () => {
        running = false;
      },
    };
    finishers.push(() => {
      running = false;
      playState = "finished";
      animation.onfinish?.();
    });
    return animation as unknown as Animation;
  }) as typeof Element.prototype.animate;

  /** Let the newest roll play out, as the browser would. */
  const settle = () => act(() => finishers[finishers.length - 1]?.());
  return { rolls, box, settle, hold: (height: number) => { box.displayed = height; } };
}

function stubMotionPreference(reduce: boolean): void {
  vi.spyOn(window, "matchMedia").mockReturnValue({
    matches: reduce,
    media: "(prefers-reduced-motion: reduce)",
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  } as MediaQueryList);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Collapse", () => {
  it("renders nothing while shut", () => {
    render(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    expect(screen.queryByText("rows")).toBeNull();
  });

  it("rolls open from nothing to its content height, fading in as it goes", () => {
    const { rolls } = stubBrowser();
    const view = render(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    view.rerender(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    expect(screen.getByText("rows")).toBeInTheDocument();
    expect(rolls).toEqual([{ from: 0, to: HEIGHT, fade: [0, 1] }]);
  });

  it("stays mounted through the roll shut, which is the whole point of it", () => {
    const { rolls, settle } = stubBrowser();
    const view = render(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    view.rerender(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    // React would have deleted the rows here, the content below would have snapped up into the
    // hole, and only then would the panel have eased down after it. Instead they are still on
    // screen, rolling shut, and the panel's `auto` height follows them.
    expect(screen.getByText("rows")).toBeInTheDocument();
    expect(rolls).toEqual([{ from: HEIGHT, to: 0, fade: [1, 0] }]);
    settle();
    expect(screen.queryByText("rows")).toBeNull();
  });

  it("claims the motion while it runs, so the panel leaves the height alone", () => {
    const { settle } = stubBrowser();
    const view = render(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    view.rerender(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    expect(view.container.querySelector("[data-morphing]")).not.toBeNull();
    settle();
    expect(view.container.querySelector("[data-morphing]")).toBeNull();
  });

  it("tells the panel when it stops, since rolling open changes no state to notice", () => {
    const { settle } = stubBrowser();
    const heard: string[] = [];
    const view = render(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    // Listening on the container, not on the section: it bubbles, so the panel hears it without
    // the section having to know the panel is there.
    view.container.addEventListener("cortex:morphend", () => heard.push("end"));
    view.rerender(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    expect(heard).toEqual([]);
    settle();
    expect(heard).toEqual(["end"]);
  });

  it("carries on from where it had got to when reopened mid-roll", () => {
    const { rolls, hold } = stubBrowser();
    const view = render(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    view.rerender(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    // Half way shut, and asked to open again: the second roll starts where the eye is, not from
    // zero, so the reversal is continuous rather than a jump back to nothing.
    hold(70);
    view.rerender(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    expect(rolls[1]).toEqual({ from: 70, to: HEIGHT, fade: [0, 1] });
  });

  it("does nothing on a re-render that did not change anything", () => {
    const { rolls } = stubBrowser();
    const view = render(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    view.rerender(
      <Collapse open>
        <p>other rows</p>
      </Collapse>,
    );
    expect(rolls).toEqual([]);
  });

  it("skips the roll when there is nothing to see, closing at once", () => {
    const { rolls, box } = stubBrowser();
    box.natural = 1;
    const view = render(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    view.rerender(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    expect(rolls).toEqual([]);
    expect(screen.queryByText("rows")).toBeNull();
  });

  it("schedules nothing under prefers-reduced-motion", () => {
    const { rolls } = stubBrowser();
    stubMotionPreference(true);
    const view = render(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    view.rerender(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    expect(rolls).toEqual([]);
    expect(screen.queryByText("rows")).toBeNull();
  });
});
