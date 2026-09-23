import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { laysEverything } from "../test-setup";
import { Collapse } from "./Collapse";

const HEIGHT = 120;
/** A content height with a sub-pixel in it, which is the common case in a real layout: measured
 *  over the demo at 900x1000, the reminder stack's aside stands at 193.75px and a row at 57.25. */
const HALF = 76.75;

interface Roll {
  readonly from: number;
  readonly to: number;
  readonly fade: readonly [number, number];
}

/** jsdom has neither the Web Animations API nor layout, so both are stood in for. */
function stubBrowser() {
  const rolls: Roll[] = [];
  const fills: string[] = [];
  const cancelled: number[] = [];
  const finishers: (() => void)[] = [];
  const box = { natural: HEIGHT, displayed: 0 };
  let running = false;
  let playState: AnimationPlayState = "running";

  laysEverything(() => (running ? box.displayed : box.natural));

  Element.prototype.animate = ((keyframes: Keyframe[], options: KeyframeAnimationOptions) => {
    const read = (frame: Keyframe | undefined) => ({
      height: Number.parseFloat(String(frame?.height ?? "0")),
      opacity: Number(frame?.opacity ?? 0),
    });
    const from = read(keyframes[0]);
    const to = read(keyframes[1]);
    rolls.push({ from: from.height, to: to.height, fade: [from.opacity, to.opacity] });
    fills.push(String(options.fill ?? "none"));
    running = true;
    const index = rolls.length;
    const animation = {
      get playState() {
        return playState;
      },
      onfinish: null as (() => void) | null,
      cancel: () => {
        running = false;
        cancelled.push(index);
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
  return {
    rolls,
    fills,
    cancelled,
    box,
    settle,
    hold: (height: number) => {
      box.displayed = height;
    },
  };
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

  it("rolls to the sub-pixel its content actually stands on, opening and shutting alike", () => {
    const { box, rolls, settle } = stubBrowser();
    box.natural = HALF;
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
    expect(rolls).toEqual([{ from: 0, to: HALF, fade: [0, 1] }]);
    expect(view.container.querySelector("[data-morphing]")).toHaveAttribute(
      "data-morphing",
      String(HALF),
    );
    settle();
    view.rerender(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    expect(rolls[1]).toEqual({ from: HALF, to: 0, fade: [1, 0] });
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
    expect(screen.getByText("rows")).toBeInTheDocument();
    expect(rolls).toEqual([{ from: HEIGHT, to: 0, fade: [1, 0] }]);
    settle();
    expect(screen.queryByText("rows")).toBeNull();
  });

  it("holds its collapsed height until React removes it, so nothing paints at the old size", () => {
    const { fills, settle } = stubBrowser();
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
    expect(fills).toEqual(["forwards"]);
    settle();
    view.rerender(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    expect(fills).toEqual(["forwards", "none"]);
  });

  it("releases the held height when reopened, so it rolls from nothing and not from a stuck one", () => {
    const { rolls, cancelled, settle } = stubBrowser();
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
    settle();
    view.rerender(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    expect(cancelled).toEqual([1]);
    expect(rolls[1]).toEqual({ from: 0, to: HEIGHT, fade: [0, 1] });
  });

  it("claims the motion while it runs, saying which height it is rolling to", () => {
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
    expect(view.container.querySelector("[data-morphing]")?.getAttribute("data-morphing")).toBe(
      String(HEIGHT),
    );
    settle();
    expect(view.container.querySelector("[data-morphing]")).toBeNull();

    view.rerender(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    expect(view.container.querySelector("[data-morphing]")?.getAttribute("data-morphing")).toBe("0");
  });

  it("tells the panel when it starts, since not every roll is a render the panel can see", () => {
    const { settle } = stubBrowser();
    const heard: (string | null)[] = [];
    const view = render(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    view.container.addEventListener("cortex:morphstart", (event) =>
      heard.push((event.target as HTMLElement).getAttribute("data-morphing")),
    );
    view.rerender(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    expect(heard).toEqual([String(HEIGHT)]);
    settle();
    view.rerender(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    expect(heard).toEqual([String(HEIGHT), "0"]);
  });

  it("announces no start when there is no roll to move with", () => {
    stubMotionPreference(true);
    stubBrowser();
    const heard: string[] = [];
    const view = render(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    view.container.addEventListener("cortex:morphstart", () => heard.push("start"));
    view.rerender(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    expect(heard).toEqual([]);
  });

  it("tells the panel when it stops, since rolling open changes no state to notice", () => {
    const { settle } = stubBrowser();
    const heard: string[] = [];
    const view = render(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
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

  it("continues from where it had got to when reopened mid-roll", () => {
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

  it("rolls in on mount when told to, and only then", () => {
    const { rolls } = stubBrowser();
    const view = render(
      <Collapse open enter>
        <p>rows</p>
      </Collapse>,
    );
    expect(rolls).toEqual([{ from: 0, to: HEIGHT, fade: [0, 1] }]);
    view.rerender(
      <Collapse open enter>
        <p>rows</p>
      </Collapse>,
    );
    expect(rolls).toHaveLength(1);
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

  it("schedules nothing under prefers-reduced-motion, and announces no start either", () => {
    const { rolls } = stubBrowser();
    stubMotionPreference(true);
    const started: string[] = [];
    const view = render(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    view.container.addEventListener("cortex:morphstart", () => started.push("start"));
    view.rerender(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    expect(rolls).toEqual([]);
    expect(screen.queryByText("rows")).toBeNull();
    expect(started).toEqual([]);
  });

  it("is already collapsed when it tells the panel so, with no animation to hold it there", () => {
    stubMotionPreference(true);
    stubBrowser();
    const view = render(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    let heightWhenTold: string | undefined;
    view.container.addEventListener("cortex:morphend", (event) => {
      heightWhenTold = (event.target as HTMLElement).style.height;
    });
    view.rerender(
      <Collapse open={false}>
        <p>rows</p>
      </Collapse>,
    );
    expect(heightWhenTold).toBe("0px");
  });

  it("hands the closed section back to its caller, and only once it is shut", () => {
    const { settle } = stubBrowser();
    const onClosed = vi.fn();
    const view = render(
      <Collapse open onClosed={onClosed}>
        <p>rows</p>
      </Collapse>,
    );
    view.rerender(
      <Collapse open={false} onClosed={onClosed}>
        <p>rows</p>
      </Collapse>,
    );
    expect(onClosed).not.toHaveBeenCalled();
    settle();
    expect(onClosed).toHaveBeenCalledTimes(1);
  });

  it("says nothing to its caller on the way open, there being nothing to take away", () => {
    const { settle } = stubBrowser();
    const onClosed = vi.fn();
    const view = render(
      <Collapse open={false} onClosed={onClosed}>
        <p>rows</p>
      </Collapse>,
    );
    view.rerender(
      <Collapse open onClosed={onClosed}>
        <p>rows</p>
      </Collapse>,
    );
    settle();
    expect(onClosed).not.toHaveBeenCalled();
  });

  it("is still in the tree when the panel re-measures, and released only after", () => {
    const { settle } = stubBrowser();
    const seen: string[] = [];
    const view = render(
      <Collapse open onClosed={() => seen.push("released")}>
        <p>rows</p>
      </Collapse>,
    );
    view.container.addEventListener("cortex:morphend", (event) => {
      seen.push(view.container.contains(event.target as Node) ? "measured" : "measured off-tree");
    });
    view.rerender(
      <Collapse open={false} onClosed={() => seen.push("released")}>
        <p>rows</p>
      </Collapse>,
    );
    settle();
    expect(seen).toEqual(["measured", "released"]);
  });
});
