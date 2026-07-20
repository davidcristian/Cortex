import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { lobePath } from "../mark/bubble";
import { ORBIT_MARK, PING, WOBBLE } from "../mark/marks";
import { STILL_SECONDS } from "../mark/useMarkClock";
import { BubbleMark } from "./BubbleMark";

/** Take over the frame loop so the test drives the mark's clock by hand. */
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

const outline = (container: HTMLElement): string | null =>
  container.querySelector("path.mark-body")?.getAttribute("d") ?? null;

afterEach(() => {
  vi.restoreAllMocks();
});

describe("BubbleMark", () => {
  it("draws one bubble per lobe, sized and hidden from assistive tech", () => {
    const { container } = render(
      <BubbleMark style={WOBBLE} size={64} idPrefix="orb" animated={false} />,
    );
    const svg = container.querySelector("svg.mark");
    expect(svg).toHaveAttribute("width", "64");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelectorAll("path.mark-body")).toHaveLength(1);
    expect(container.querySelectorAll("clipPath")).toHaveLength(1);
  });

  it("draws the cluster style as three clipped lobes", () => {
    const { container } = render(
      <BubbleMark style={ORBIT_MARK} size={54} idPrefix="empty" animated={false} />,
    );
    expect(container.querySelectorAll("path.mark-body")).toHaveLength(3);
    expect(container.querySelectorAll("clipPath")).toHaveLength(3);
    expect(container.querySelector("#empty-clip2")).not.toBeNull();
  });

  it("holds the still pose, exactly the geometry the model gives, when not animated", () => {
    const { container } = render(
      <BubbleMark style={WOBBLE} size={64} idPrefix="orb" animated={false} />,
    );
    const lobe = WOBBLE.lobes[0];
    expect(lobe).toBeDefined();
    expect(outline(container)).toBe(lobe && lobePath(lobe, STILL_SECONDS));
  });

  it("warps the outline as its clock advances", () => {
    const tick = fakeFrames();
    const { container } = render(
      <BubbleMark style={WOBBLE} size={64} idPrefix="orb" animated={true} />,
    );
    tick(1000);
    const early = outline(container);
    tick(3200);
    expect(outline(container)).not.toBe(early);
    // The film turns with the same clock, in opposite directions for the two bands.
    const film = container.querySelector("#orb-film")?.getAttribute("gradientTransform");
    const inner = container.querySelector("#orb-inner")?.getAttribute("gradientTransform");
    expect(film).toMatch(/^rotate\(30\.46 50 50\)$/u);
    expect(inner).toMatch(/^rotate\(-19\.80 50 50\)$/u);
  });

  it("brightens the film with each crest for a ping style, and holds it steady otherwise", () => {
    const still = render(<BubbleMark style={WOBBLE} size={64} idPrefix="a" animated={false} />);
    const pinged = render(<BubbleMark style={PING} size={64} idPrefix="b" animated={false} />);
    const opacityOf = (view: typeof still): number =>
      Number(view.container.querySelector("path.mark-film")?.getAttribute("opacity"));
    expect(opacityOf(still)).toBeCloseTo(0.85, 5);
    expect(opacityOf(pinged)).toBeLessThan(opacityOf(still));
  });

  it("keeps its gradient and clip ids unique, so co-existing marks never borrow each other's", () => {
    const { container } = render(
      <>
        <BubbleMark style={WOBBLE} size={64} idPrefix="orb" animated={false} />
        <BubbleMark style={PING} size={34} idPrefix="pick-ping" animated={false} />
      </>,
    );
    const ids = [...container.querySelectorAll("linearGradient, radialGradient, clipPath")].map(
      (node) => node.id,
    );
    expect(new Set(ids).size).toBe(ids.length);
    expect(container.querySelector("#pick-ping-film")).not.toBeNull();
    expect(container.querySelectorAll("path.mark-rim")[1]).toHaveAttribute(
      "stroke",
      "url(#pick-ping-film)",
    );
  });
});
