// Test harness glue (excluded from coverage): jest-dom matchers, DOM cleanup between tests, a
// matchMedia stub (jsdom omits it) so the theme resolver can read the system scheme, a
// ResizeObserver stand-in (jsdom omits that too), and the roll stand-in every per-row exit is
// asserted through.
import "@testing-library/jest-dom/vitest";
import { act, cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

/**
 * A `ResizeObserver` that observes what the real one observes and reports when a test says the box
 * moved, jsdom having no layout to notice it for itself.
 *
 * Faithful in the way that matters: the callback fires for the element that was observed and only
 * while it is observed, so a test asserting that the panel re-places on its own growth is asserting
 * the subscription as well as the placement. `resizePanel` is the browser's frame, called by hand.
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

/** How tall a rolling section measures while `stubRoll` is installed. Any value past
 *  `MIN_DELTA_PX` will do: what it buys is a roll that actually runs rather than one `Collapse`
 *  completes on the spot. */
const ROLL_PX = 48;

/**
 * Stand in for the two things jsdom does not have, so a `Collapse` exit can be observed mid-roll.
 *
 * jsdom has neither layout nor the Web Animations API, so without this a row's exit finishes inside
 * the layout effect that starts it and a row is never observably on its way out. The stand-in is
 * faithful in the one way that matters: a cancelled animation never finishes, which is what a row
 * coming back mid-exit depends on. Returns the way to land every roll still in the air.
 *
 * Shared by the two lists that roll their rows out one at a time (the reminder stack and the chat
 * switcher), so the fake they both assert against is one fake. Restoring it is the caller's:
 * `vi.restoreAllMocks()` in the file's own `afterEach` puts `offsetHeight` back.
 */
export function stubRoll(): () => void {
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(ROLL_PX);
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
