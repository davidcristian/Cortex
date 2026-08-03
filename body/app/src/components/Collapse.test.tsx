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
  // Which end state each roll holds after it finishes, and which held ones were released again.
  const fills: string[] = [];
  const cancelled: number[] = [];
  const finishers: (() => void)[] = [];
  const box = { natural: HEIGHT, displayed: 0 };
  let running = false;
  let playState: AnimationPlayState = "running";

  // The section reads its own LAYOUT height, which is `offsetHeight` and not the rect: the panel
  // around it is scaled through a summon, and the rect is measured after that transform.
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockImplementation(() =>
    running ? box.displayed : box.natural,
  );

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
    // The opening direction holds nothing: its end state IS the natural height, so there is
    // nothing to hold, and holding it would freeze the section at the content it opened with.
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
    // The finished closing roll is still holding 0; letting go of it is what lets the section
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
    // The value is the contract, not just the presence: the panel works out from it how tall IT is
    // about to be, and moves its own bottom edge over this same roll instead of after it.
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
    // What the panel needs at this moment is the height being rolled to, so the attribute has to be
    // set by the time the event lands: it works out from that number how tall it is about to be and
    // takes its own bottom edge along over the same roll.
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
    // Nothing is animating, so there is nothing for the panel to ride along WITH: the end event
    // that follows immediately is what places it around the height already committed to.
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

  it("rolls in on mount when told to, and only then", () => {
    const { rolls } = stubBrowser();
    // A section mounted with the view it belongs to is already there and animates only what
    // happens to it afterwards (the re-render case above). One mounted INTO a list that is on
    // screen has arrived, and the switcher's empty line is that case: it takes the place of the
    // last row as that row rolls out, so it has to grow into the gap on the same clock.
    const view = render(
      <Collapse open enter>
        <p>rows</p>
      </Collapse>,
    );
    expect(rolls).toEqual([{ from: 0, to: HEIGHT, fade: [0, 1] }]);
    // Read once, at mount: a section already on screen cannot arrive again.
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

  it("is already collapsed when it tells the panel so, with no animation to hold it there", () => {
    stubMotionPreference(true);
    stubBrowser();
    const view = render(
      <Collapse open>
        <p>rows</p>
      </Collapse>,
    );
    // What the panel sees when it re-measures on the event: with nothing animating, there is no
    // forwards fill holding the end state, so the section would still be standing at its full
    // height around rows that are about to go. Traced under prefers-reduced-motion before this was
    // fixed: closing the chat switcher left the panel 119px lower than it had been before it
    // opened, and it stayed there, because that was the height it was placed around.
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
    // What lets a list hold a removed row until its own exit ends (`overlay/usePresence.ts`):
    // the roll owns the clock, and this is the roll saying it is over.
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
    // The order these two land in is the contract: the panel places itself off the event, so the
    // section has to be part of what it measures. Told first, the caller would be free to take the
    // element away before the panel had heard the roll end at all.
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
