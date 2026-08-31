// Test setup, excluded from coverage: jest-dom matchers, DOM cleanup between tests, stand-ins for
// the `matchMedia` and `ResizeObserver` that jsdom leaves out, the laid-out heights a test gives
// the boxes the panel measures, and the animation stand-in the per-row exits are asserted through.
import "@testing-library/jest-dom/vitest";
import { act, cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

/** A `ResizeObserver` for jsdom, which has no layout and so never reports a box changing size.
 *  The callback runs only while the element is observed, and `resized` delivers by hand the
 *  notification a browser would deliver. */
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

/** How tall a box measures, through the one property production reads: the used height off the
 *  computed style. jsdom has no layout and returns the empty string for every height, so a test
 *  that needs a box says how tall it is here. Faking `offsetHeight` would fake an unread number. */
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
 *  is an element it cannot reach, such as the empty state, which publishes `--chat-floor` during
 *  the same render that mounts it. */
export function laysEverything(height: number | (() => number)): () => void {
  laidOutAll = typeof height === "number" ? () => height : height;
  return () => {
    laidOutAll = null;
  };
}

/** How tall a rolling section measures while `stubRoll` is installed. Any value above
 *  `MIN_DELTA_PX` will do; below it `Collapse` finishes the roll at once instead of running one. */
const ROLL_PX = 48;

/** Stand in for the layout and the Web Animations API that jsdom does not have, so a `Collapse`
 *  exit can be watched mid-roll. It reproduces the one behavior those tests need: a cancelled
 *  animation never finishes. Returns the way to finish every roll still running. */
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
