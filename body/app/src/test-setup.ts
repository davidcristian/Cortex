// Test harness glue (excluded from coverage): jest-dom matchers, DOM cleanup between tests, a
// matchMedia stub (jsdom omits it) so the theme resolver can read the system scheme, a
// ResizeObserver stand-in (jsdom omits that too), the laid-out heights tests give the boxes the
// panel measures, and the animation stand-in the per-row exits are asserted through.
import "@testing-library/jest-dom/vitest";
import { act, cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

/**
 * A `ResizeObserver` for jsdom, which has no layout and so never reports a box changing size.
 *
 * The callback fires for the element that was observed and only while it is observed, so a test
 * asserting that the panel re-places on its own growth is asserting the subscription as well as the
 * placement. `resized` delivers the notification the browser would deliver, called by hand.
 */
class FakeResizeObserver implements ResizeObserver {
  private readonly watched = new Set<Element>();

  constructor(private readonly callback: ResizeObserverCallback) {
    watchers.add(this);
  }

  observe(target: Element): void {
    this.watched.add(target);
  }

  unobserve(target: Element): void {
    this.watched.delete(target);
  }

  disconnect(): void {
    this.watched.clear();
    watchers.delete(this);
  }

  /** Deliver a notification for `target`, if this observer is watching it. */
  deliver(target: Element): boolean {
    if (!this.watched.has(target)) {
      return false;
    }
    this.callback([{ target } as ResizeObserverEntry], this);
    return true;
  }
}

const watchers = new Set<FakeResizeObserver>();

/** Tell every observer watching `target` that its box changed, and answer how many heard it. */
export function resized(target: Element): number {
  let heard = 0;
  for (const watcher of [...watchers]) {
    heard += watcher.deliver(target) ? 1 : 0;
  }
  return heard;
}

globalThis.ResizeObserver = FakeResizeObserver;

/**
 * How tall a box measures, answered through the one property production reads.
 *
 * The panel's own measurement is the used height off the computed style (`panelMemory.heightOf`),
 * which is the reading that keeps its sub-pixels and ignores the summon's scale transform, and a
 * section's roll measures itself with the same function so the two cannot disagree. jsdom has no
 * layout and answers every height with the empty string, so a test that needs a box says how tall
 * it is here. Faking `offsetHeight` instead would fake a number nothing measures.
 *
 * A function rather than a number where the height changes under the test: a box mid-animation, or
 * one whose answer depends on the cap standing on the element.
 */
const laidOut = new WeakMap<Element, () => number>();
/** Every box at once, for the tests that measure an element they never get their hands on. */
let laidOutAll: (() => number) | null = null;
const computedStyle = window.getComputedStyle.bind(window);
window.getComputedStyle = ((element: Element, pseudo?: string | null) => {
  const declaration = computedStyle(element, pseudo ?? undefined);
  const height = laidOut.get(element) ?? laidOutAll;
  if (height === null) {
    return declaration;
  }
  return new Proxy(declaration, {
    get(target, key) {
      if (key === "height") {
        return `${height()}px`;
      }
      const value = Reflect.get(target, key) as unknown;
      return typeof value === "function" ? (value as () => unknown).bind(target) : value;
    },
  });
}) as typeof window.getComputedStyle;

/** Give `element` a laid-out height, as a number or as an answer that can change under the test. */
export function lays(element: Element, height: number | (() => number)): void {
  laidOut.set(element, typeof height === "number" ? () => height : height);
}

/** Give every box the same laid-out height, and return the way to stop. For a test whose subject
 *  is an element it cannot reach: `Panel`'s empty state publishes `--chat-floor` during the render
 *  that mounts it, so there is no moment in between to hand it a height, and a rolling section is
 *  measured inside the layout effect that mounts it. A function where the answer changes under the
 *  test, as it does mid-roll: a running height animation overrides the used height, so a roll
 *  interrupted half way reads where it had got to rather than what its content is worth. */
export function laysEverything(height: number | (() => number)): () => void {
  laidOutAll = typeof height === "number" ? () => height : height;
  return () => {
    laidOutAll = null;
  };
}

/** How tall a rolling section measures while `stubRoll` is installed. Any value past
 *  `MIN_DELTA_PX` will do; under it `Collapse` completes the roll on the spot instead of running
 *  one. */
const ROLL_PX = 48;

/**
 * Stand in for the two things jsdom does not have, so a `Collapse` exit can be observed mid-roll.
 *
 * jsdom has neither layout nor the Web Animations API, so without this a row's exit finishes inside
 * the layout effect that starts it and a row is never observably on its way out. The stand-in
 * reproduces the one behaviour those tests depend on: a cancelled animation never finishes, which
 * is what a row coming back mid-exit relies on. Returns the way to land every roll still in the
 * air.
 *
 * Shared by the two lists that roll their rows out one at a time (the reminder stack and the chat
 * switcher), so the fake they both assert against is one fake. The height is given through the
 * computed style, because that is where `Collapse` reads the height it rolls to (`heightOf`); faked
 * on `offsetHeight` it would be a number production no longer looks at. Restoring the height is the
 * file's `afterEach` here rather than the caller's.
 */
export function stubRoll(): () => void {
  laysEverything(ROLL_PX);
  const finishers: (() => void)[] = [];
  Element.prototype.animate = (() => {
    let live = true;
    const animation = {
      get playState(): AnimationPlayState {
        return live ? "running" : "idle";
      },
      onfinish: null as (() => void) | null,
      cancel: () => {
        live = false;
      },
    };
    finishers.push(() => {
      if (live) {
        animation.onfinish?.();
      }
    });
    return animation as unknown as Animation;
  }) as typeof Element.prototype.animate;
  return () => act(() => finishers.splice(0).forEach((land) => land()));
}

afterEach(() => {
  cleanup();
  watchers.clear();
  laidOutAll = null;
});

window.matchMedia = ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: () => undefined,
  removeEventListener: () => undefined,
  addListener: () => undefined,
  removeListener: () => undefined,
  dispatchEvent: () => false,
})) as typeof window.matchMedia;
