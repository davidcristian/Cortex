import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LUCID, REVERIE, STILL, TRANCE } from "../edge/edges";
import { EdgeMini } from "./EdgeMini";

describe("EdgeMini", () => {
  it("draws the still edge as one resting shape with no glow and no gradient", () => {
    const { container } = render(<EdgeMini style={STILL} idPrefix="m1" animated={false} />);
    const svg = container.querySelector("svg.edge-mini");
    expect(svg).toHaveAttribute("viewBox", "0 0 72 50");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelector("linearGradient")).toBeNull();
    expect(container.querySelector(".edge-mini-glow")).toBeNull();
    // Glass and hairline are the same outline, filled and stroked.
    const glass = container.querySelector(".edge-mini-glass")?.getAttribute("d");
    expect(glass).toBe(container.querySelector(".edge-mini-line")?.getAttribute("d"));
  });

  it("shows each glowing liquid's color signature at rest, so the tiles can be told apart", () => {
    // Lucid is a liquid without a glow: its tile is the moving outline alone, which is also what
    // separates it from Reverie in the row.
    const strict = render(<EdgeMini style={LUCID} idPrefix="m1b" animated={false} />);
    expect(strict.container.querySelector(".edge-mini-glow")).toBeNull();
    const settled = render(<EdgeMini style={REVERIE} idPrefix="m2" animated={false} />);
    const glow = settled.container.querySelector(".edge-mini-glow");
    expect(glow?.getAttribute("class")).toBe("edge-mini-glow settled");
    expect(glow).toHaveAttribute("stroke", "url(#m2-ember)");
    const ember = render(<EdgeMini style={TRANCE} idPrefix="m3" animated={false} />);
    expect(ember.container.querySelector(".edge-mini-glow")?.getAttribute("class")).toBe(
      "edge-mini-glow ember",
    );
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
