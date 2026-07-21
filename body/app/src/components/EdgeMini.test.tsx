import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LUCID, REVERIE, STILL, TRANCE } from "../edge/edges";
import { EdgeMini } from "./EdgeMini";

describe("EdgeMini", () => {
  it("draws the still edge as one resting portrait with no glow and no gradient", () => {
    const { container } = render(<EdgeMini style={STILL} idPrefix="m1" animated={false} />);
    const svg = container.querySelector("svg.edge-mini");
    expect(svg).toHaveAttribute("viewBox", "0 0 72 50");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelector("linearGradient")).toBeNull();
    expect(container.querySelector(".edge-mini-glow")).toBeNull();
    // The portrait's furniture: the little window's title, reply and composer, and NO ground of
    // its own, the tile being the ground it floats on.
    expect(container.querySelector(".edge-mini-ground")).toBeNull();
    expect(container.querySelectorAll(".edge-mini-bar")).toHaveLength(2);
    expect(container.querySelector(".edge-mini-pill")).not.toBeNull();
    // Glass and hairline are the same outline, filled and stroked.
    const glass = container.querySelector(".edge-mini-glass")?.getAttribute("d");
    expect(glass).toBe(container.querySelector(".edge-mini-line")?.getAttribute("d"));
  });

  it("shows each liquid's signature, and Lucid none, so the tiles can be told apart", () => {
    // Lucid is a liquid without a glow: its tile is the moving outline alone, which is also
    // what separates it from Reverie in the row.
    const strict = render(<EdgeMini style={LUCID} idPrefix="m1b" animated={false} />);
    expect(strict.container.querySelector(".edge-mini-glow")).toBeNull();
    // Trance's ember is constant: one accent stroke, no neutral twin, no cycle.
    const ember = render(<EdgeMini style={TRANCE} idPrefix="m3" animated={false} />);
    const glows = ember.container.querySelectorAll(".edge-mini-glow");
    expect(glows).toHaveLength(1);
    expect(glows[0]?.getAttribute("class")).toBe("edge-mini-glow ember");
    expect(glows[0]).toHaveAttribute("stroke", "url(#m3-ember)");
    expect((glows[0] as SVGPathElement).style.opacity).toBe("");
  });

  it("freezes Reverie exactly mid-blend, so a still tile shows both of its states at once", () => {
    // Reverie IS the change between a neutral rest and the accent while working: frozen in the
    // accent alone it read as a lighter Trance (the maintainer's words), which is Trance's identity,
    // not Reverie's. Animated, the two strokes cross-fade on a slow cycle; frozen, the phase is
    // chosen so the pose splits the difference and both truths show at once.
    const { container } = render(<EdgeMini style={REVERIE} idPrefix="m2" animated={false} />);
    const rest = container.querySelector(".edge-mini-glow.rest") as SVGPathElement;
    const accent = container.querySelector(".edge-mini-glow.settled") as SVGPathElement;
    expect(accent).toHaveAttribute("stroke", "url(#m2-ember)");
    expect(rest.getAttribute("d")).toBe(accent.getAttribute("d"));
    expect(Number.parseFloat(rest.style.opacity)).toBeCloseTo(0.2, 5);
    expect(Number.parseFloat(accent.style.opacity)).toBeCloseTo(0.25, 5);
  });

  it("keeps its gradient ids unique, so co-existing tiles never borrow each other's", () => {
    const { container } = render(
      <>
        <EdgeMini style={REVERIE} idPrefix="a" animated={false} />
        <EdgeMini style={TRANCE} idPrefix="b" animated={false} />
      </>,
    );
    const ids = [...container.querySelectorAll("linearGradient")].map((node) => node.id);
    expect(ids).toEqual(["a-ember", "b-ember"]);
  });
});
