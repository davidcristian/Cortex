import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RingMark } from "./RingMark";

describe("RingMark", () => {
  it("renders two gradient-stroked bands sized as asked", () => {
    const { container } = render(<RingMark size={64} idPrefix="orb" strokeWidth={2.5} />);
    const svg = container.querySelector("svg.rings");
    expect(svg).toHaveAttribute("width", "64");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    const bands = container.querySelectorAll("path.ring");
    expect(bands).toHaveLength(2);
    expect(bands[0]).toHaveAttribute("stroke", "url(#orb-band-a)");
    expect(bands[1]).toHaveAttribute("stroke", "url(#orb-band-b)");
  });

  it("keeps gradient ids unique across co-existing marks", () => {
    const { container } = render(
      <>
        <RingMark size={64} idPrefix="orb" strokeWidth={2.5} />
        <RingMark size={14} idPrefix="pv" strokeWidth={5} />
      </>,
    );
    const ids = [...container.querySelectorAll("linearGradient")].map((node) => node.id);
    expect(new Set(ids).size).toBe(4);
    expect(container.querySelector("#pv-band-a")).not.toBeNull();
  });
});
