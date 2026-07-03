import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RingMark } from "./RingMark";

describe("RingMark", () => {
  it("renders two gradient-stroked bands with depth pulses when animated", () => {
    const { container } = render(
      <RingMark size={64} idPrefix="orb" strokeWidth={2.5} animated={true} />,
    );
    const svg = container.querySelector("svg.rings");
    expect(svg).toHaveAttribute("width", "64");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    const bands = container.querySelectorAll("path.ring");
    expect(bands).toHaveLength(2);
    expect(bands[0]).toHaveAttribute("stroke", "url(#orb-band-a)");
    expect(bands[1]).toHaveAttribute("stroke", "url(#orb-band-b)");
    const pulses = container.querySelectorAll("animate");
    expect(pulses).toHaveLength(2);
    expect(pulses[0]).toHaveAttribute("attributeName", "d");
    expect(pulses[0]?.getAttribute("values")?.split(";")).toHaveLength(3);
  });

  it("renders still (no pulses) when not animated, with unique ids across marks", () => {
    const { container } = render(
      <>
        <RingMark size={64} idPrefix="orb" strokeWidth={2.5} animated={false} />
        <RingMark size={14} idPrefix="pv" strokeWidth={5} animated={false} />
      </>,
    );
    expect(container.querySelectorAll("animate")).toHaveLength(0);
    const ids = [...container.querySelectorAll("linearGradient")].map((node) => node.id);
    expect(new Set(ids).size).toBe(4);
    expect(container.querySelector("#pv-band-a")).not.toBeNull();
  });
});
