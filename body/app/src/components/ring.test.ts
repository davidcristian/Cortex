import { describe, expect, it } from "vitest";

import { wavyRingPath } from "./ring";

/** Parse "M x y L x y … Z" back into points. */
function points(path: string): readonly { x: number; y: number }[] {
  const body = path.replace(/^M /u, "").replace(/ Z$/u, "");
  return body.split(" L ").map((pair) => {
    const [x, y] = pair.split(" ").map(Number);
    return { x: x ?? Number.NaN, y: y ?? Number.NaN };
  });
}

describe("wavyRingPath", () => {
  it("closes the path and honors the sample count", () => {
    const path = wavyRingPath(32, 22, 3, 7, 0, 90);
    expect(path.startsWith("M ")).toBe(true);
    expect(path.endsWith(" Z")).toBe(true);
    expect(points(path)).toHaveLength(90);
  });

  it("stays within radius ± amplitude of the center", () => {
    const radii = points(wavyRingPath(32, 22, 3, 7, 0, 360)).map(({ x, y }) =>
      Math.hypot(x - 32, y - 32),
    );
    expect(Math.min(...radii)).toBeGreaterThanOrEqual(19 - 0.01);
    expect(Math.max(...radii)).toBeLessThanOrEqual(25 + 0.01);
    expect(Math.max(...radii) - Math.min(...radii)).toBeGreaterThan(5);
  });

  it("waves the radius the requested number of times per revolution", () => {
    // Phase 0.3 keeps every sample clear of the sine's zeros, so the strict sign-change
    // count below is immune to the path's 2-decimal coordinate rounding.
    const radii = points(wavyRingPath(0, 10, 1, 5, 0.3, 500)).map(({ x, y }) => Math.hypot(x, y));
    let crossings = 0;
    for (let index = 0; index < radii.length; index += 1) {
      const here = (radii[index] ?? 10) - 10;
      const next = (radii[(index + 1) % radii.length] ?? 10) - 10;
      if (here * next < 0) {
        crossings += 1;
      }
    }
    expect(crossings).toBe(10);
  });

  it("shifts the pattern with phase and defaults to a fine sampling", () => {
    expect(wavyRingPath(32, 22, 3, 7, 0)).not.toBe(wavyRingPath(32, 22, 3, 7, 1));
    expect(points(wavyRingPath(32, 22, 3, 7, 0))).toHaveLength(180);
  });
});
