import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LUCID, REVERIE, TRANCE } from "../edge/edges";
import { BLEED } from "../edge/liquid";
import { PanelEdge } from "./PanelEdge";

/** Take over the frame loop so the test drives the edge's clock by hand. */
function fakeFrames() {
  const callbacks: FrameRequestCallback[] = [];
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
    callbacks.push(callback);
    return callbacks.length;
  });
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined);
  return (now: number): void => {
    const next = callbacks.shift();
    act(() => next?.(now));
  };
}

/** jsdom has no layout, so the box the edge measures itself against is stubbed. */
function stubBox(width: number, height: number) {
  vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(width);
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(height);
}

const hairOf = (container: HTMLElement): string =>
  container.querySelector("path.edge-hair")?.getAttribute("d") ?? "";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("PanelEdge", () => {
  it("layers the clipped slab, the glow under, and the hairline over, sized to its box", () => {
    stubBox(560, 480);
    const { container } = render(
      <PanelEdge style={REVERIE} working={false} animated={false} idPrefix="t1" />,
    );
    const wrapper = container.querySelector(".edge") as HTMLElement;
    expect(wrapper).toHaveAttribute("aria-hidden", "true");
    expect(wrapper.className).toBe("edge edge-settled");
    // The wrapper extends past the panel by the geometry module's own constant, so the liquid
    // swings around the panel's real edge rather than inside it.
    expect(wrapper.style.inset).toBe(`${-BLEED}px`);
    const slab = container.querySelector(".edge-glass") as HTMLElement;
    expect(slab.style.clipPath).toContain('path("M');
    // The box it measured is the box it drew: the far edge of the outline sits near 560.
    const far = Math.max(
      ...[...hairOf(container).matchAll(/L(-?[\d.]+) /gu)].map((hit) => Number(hit[1])),
    );
    expect(far).toBeGreaterThan(500);
    // A settled glow is both strokes: the neutral one and the accent one it cross-fades to.
    expect(container.querySelector(".edge-glow-n")).not.toBeNull();
    expect(container.querySelector(".edge-glow-a")).toHaveAttribute("stroke", "url(#t1-ember)");
    expect(container.querySelector("#t1-ember")).not.toBeNull();
  });

  it("keeps the ember alone and flags it, for the style whose glow never sleeps", () => {
    stubBox(560, 480);
    const { container } = render(
      <PanelEdge style={TRANCE} working={false} animated={false} idPrefix="t2" />,
    );
    expect(container.querySelector(".edge")?.className).toBe("edge edge-ember");
    expect(container.querySelector(".edge-glow-n")).toBeNull();
    expect(container.querySelector(".edge-glow-a")).not.toBeNull();
  });

  it("mounts no glow layer at all for Lucid, whose color story is fully strict", () => {
    stubBox(560, 480);
    const { container } = render(
      <PanelEdge style={LUCID} working={false} animated={false} idPrefix="t3" />,
    );
    expect(container.querySelector(".edge-under")).toBeNull();
    expect(hairOf(container)).not.toBe("");
  });

  it("snaps the working depth when not animating, so each state is one exact pose", () => {
    stubBox(560, 480);
    const { container, rerender } = render(
      <PanelEdge style={LUCID} working={false} animated={false} idPrefix="t4" />,
    );
    const resting = hairOf(container);
    rerender(<PanelEdge style={LUCID} working={true} animated={false} idPrefix="t4" />);
    expect(container.querySelector(".edge")?.className).toContain("edge-working");
    expect(hairOf(container)).not.toBe(resting);
  });

  it("re-measures through the platform's observer when its box changes size", () => {
    // jsdom has no ResizeObserver, so the observer path uses a hand-driven fake. What is asserted
    // is that the edge observes its own box, redraws to the delivered size, and disconnects on
    // unmount.
    let deliver: (() => void) | null = null;
    const disconnect = vi.fn();
    class FakeResizeObserver {
      constructor(callback: () => void) {
        deliver = callback;
      }
      observe() {}
      unobserve() {}
      disconnect = disconnect;
    }
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    const width = vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(560);
    vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(480);
    const { container, unmount } = render(
      <PanelEdge style={LUCID} working={false} animated={false} idPrefix="t6" />,
    );
    const before = hairOf(container);
    width.mockReturnValue(620);
    act(() => deliver?.());
    expect(hairOf(container)).not.toBe(before);
    // A delivery that changed nothing redraws nothing, which is what keeps the observer quiet.
    act(() => deliver?.());
    unmount();
    expect(disconnect).toHaveBeenCalledOnce();
  });

  it("advances the liquid on the frame clock and eases the depth as a movement", () => {
    stubBox(560, 480);
    const tick = fakeFrames();
    const { container, rerender } = render(
      <PanelEdge style={LUCID} working={false} animated={true} idPrefix="t5" />,
    );
    tick(1000);
    const early = hairOf(container);
    tick(2400);
    const later = hairOf(container);
    expect(later).not.toBe(early);
    // A turn starting mid-animation: the next frames move the depth toward the working value
    // instead of jumping to it, so the same clock time draws differently as the depth eases in.
    rerender(<PanelEdge style={LUCID} working={true} animated={true} idPrefix="t5" />);
    tick(2500);
    const easing = hairOf(container);
    tick(9000);
    const settled = hairOf(container);
    expect(easing).not.toBe(later);
    expect(settled).not.toBe(easing);
  });
});
