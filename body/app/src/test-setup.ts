import "@testing-library/jest-dom/vitest";
import { act, cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

/**
 * A `ResizeObserver` that observes what the real one observes and reports when a test says the box
 * moved, jsdom having no layout to notice it for itself.
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

/** How tall a box measures, said through the one property production reads. */
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

/** Give EVERY box the same laid-out height, and answer the way to stop. */
export function laysEverything(height: number | (() => number)): () => void {
  laidOutAll = typeof height === "number" ? () => height : height;
  return () => {
    laidOutAll = null;
  };
}

/** How tall a rolling section measures while `stubRoll` is installed. Any value past
 *  `MIN_DELTA_PX` will do: what it buys is a roll that actually runs rather than one `Collapse`
 *  completes on the spot. */
const ROLL_PX = 48;

/**
 * Stand in for the two things jsdom does not have, so a `Collapse` exit can be observed mid-roll.
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
