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
    expect(container.querySelector(".edge-mini-ground")).toBeNull();
    expect(container.querySelectorAll(".edge-mini-bar")).toHaveLength(2);
    expect(container.querySelector(".edge-mini-pill")).not.toBeNull();
    const glass = container.querySelector(".edge-mini-glass")?.getAttribute("d");
    expect(glass).toBe(container.querySelector(".edge-mini-line")?.getAttribute("d"));
  });

  it("shows each liquid's signature, and Lucid none, so the tiles can be told apart", () => {
    const strict = render(<EdgeMini style={LUCID} idPrefix="m1b" animated={false} />);
    expect(strict.container.querySelector(".edge-mini-glow")).toBeNull();
    const ember = render(<EdgeMini style={TRANCE} idPrefix="m3" animated={false} />);
    const glows = ember.container.querySelectorAll(".edge-mini-glow");
    expect(glows).toHaveLength(1);
    expect(glows[0]?.getAttribute("class")).toBe("edge-mini-glow ember");
    expect(glows[0]).toHaveAttribute("stroke", "url(#m3-ember)");
    expect((glows[0] as SVGPathElement).style.opacity).toBe("");
  });

  it("freezes Reverie exactly mid-blend, so a still tile shows both of its states at once", () => {
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
