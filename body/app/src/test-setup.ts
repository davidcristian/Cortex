// Test harness glue (excluded from coverage): jest-dom matchers, DOM cleanup between tests, a
// matchMedia stub (jsdom omits it) so the theme resolver can read the system scheme, and a
// ResizeObserver stand-in (jsdom omits that too).
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

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
