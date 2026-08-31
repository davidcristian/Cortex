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

/**
 * jsdom has neither the Web Animations API nor layout, so both are stood in for. The fake
 * reproduces the behaviour these tests depend on: a running animation overrides the measured
 * height, so a roll interrupted half way can be read for where it had got to.
 */
function stubBrowser() {
  const rolls: Roll[] = [];
  // Which end state each roll holds after it finishes, and which held ones were released again.
  const fills: string[] = [];
  const cancelled: number[] = [];
  const finishers: (() => void)[] = [];
  const box = { natural: HEIGHT, displayed: 0 };
  let running = false;
  let playState: AnimationPlayState = "running";

  // The section reads its own layout height off the computed style (`heightOf`), which keeps the
  // sub-pixels the roll has to land on and ignores the summon's scale transform, unlike the rect.
  // The stub answers the same call production makes, so a fractional height is a case these tests
  // can set up (`HALF`).
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
    // An opening roll deliberately does not fill, so the section returns to its own layout in the
    // frame it ends, and a target rounded off the box left it stepping the remainder. Measured over
    // the demo at 900x1000 before this, the reminder stack's aside rolled to 194 and stood at
    // 193.75, and the closing roll then started 0.25px above where it had been painted. The
    // published target carries the fraction too, since the panel adds it to fractional heights of
    // its own (`overlay/panelRide.ts`).
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
    // React would have deleted the rows here, the content below would have snapped up into the
    // gap, and only then would the panel have eased down after it. Instead the rows are still on
    // screen, rolling shut, and the panel's `auto` height follows them.
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
    // Unmounting is a React render away, so without this the element snapped back to its natural
    // height the instant the roll ended and painted there until React caught up: one frame of the
    // whole section reappearing, which is what a 60Hz trace of a switcher close showed.
    expect(fills).toEqual(["forwards"]);
    settle();
    // The opening direction holds nothing, because its end state is the natural height, so there
    // is nothing to hold and holding it would freeze the section at the content it opened with.
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
    // The finished closing roll is still holding 0, and cancelling it is what lets the section
    // measure its natural height again.
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
    // The attribute's value matters as well as its presence: the panel works out from it how tall
    // it is about to be, and moves its own bottom edge over this roll rather than after it.
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
    // The panel needs the height being rolled to, so the attribute has to be set by the time the
    // event lands: it works out from that number how tall it is about to be and moves its own
    // bottom edge over the same roll.
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

  it("announces no start when there is no roll to ride along with", () => {
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
    // Nothing is animating, so the panel has no roll to follow. The end event that follows
    // immediately is what places it around the height already committed to.
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
    // The listener is on the container rather than on the section, because the event bubbles, so
    // the panel receives it without the section holding a reference to the panel.
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
    // Half way shut and asked to open again: the second roll starts from the height currently
    // painted rather than from zero, so the reversal is continuous.
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
    // A section mounted with the view it belongs to is present from the start and animates only
    // what happens to it afterwards (the re-render case above). A section mounted into a list that
    // is already on screen is the other case, and the switcher's empty line is that case: it takes
    // the place of the last row as that row rolls out, so it grows into the gap on the same clock.
    const view = render(
      <Collapse open enter>
        <p>rows</p>
      </Collapse>,
    );
    expect(rolls).toEqual([{ from: 0, to: HEIGHT, fade: [0, 1] }]);
    // Read once, at mount, because a section already on screen cannot arrive again.
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
    // The log underneath depends on this event: its scroll follows a roll off it
    // (`overlay/logRide.ts`), so a roll that moves nothing leaves the reader's scroll position
    // alone, which is what a plain disclosure did before it was given a roll.
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
    // What the panel measures on the event: with nothing animating there is no forwards fill
    // holding the end state, so the section would still stand at its full height around rows that
    // are about to be removed. Traced under prefers-reduced-motion before this was fixed: closing
    // the chat switcher left the panel 119px lower than it had been before it opened, and it stayed
    // there, because that was the height it was placed around.
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
    // This callback is what lets a list hold a removed row until its own exit ends
    // (`overlay/usePresence.ts`): the roll holds the clock and reports when it has finished.
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
    // The order these two land in matters: the panel places itself off the event, so the section
    // has to be part of what it measures. Called first, the callback would let the caller remove
    // the element before the panel had received the roll's end event.
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
