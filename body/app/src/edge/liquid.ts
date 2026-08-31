// The window edge's geometry (ADR-0036): a rounded rectangle sampled as one closed loop, each
// point displaced along its outward normal by the style's spectrum. Pure functions of numbers, as
// mark/bubble.ts is: the component that renders this holds a clock and a box size, and nothing
// here touches the DOM.
//
// The invariant every function here maintains is that the path never leaves the given box. The box
// is the edge wrapper, which extends `BLEED` past the panel on every side, and the neutral outline
// sits exactly that far inside it, which puts it on the panel's own edge: the waves swing around
// the regular border, outward into the bleed and inward over the glass, and the registry tests
// hold every style's worst-case reach under the bleed. The first version inset the whole liquid by
// the reach instead, which on the light ground read as a window that had shrunk (ADR-0036
// decision 5).

import type { EdgeStyle } from "./edges";

/** The panel's own corner radius (overlay.css `.panel`), which the neutral line carries. */
export const CORNER_RADIUS = 28;

/** How far the edge wrapper extends past the panel's border box on every side, px. The wrapper
 *  applies it as a negative inset (PanelEdge) and the sampler applies it as the neutral line's
 *  inset, so the two cannot drift. `reachOf(style) <= BLEED` keeps every wave inside the wrapper. */
export const BLEED = 14;

/** How far past its arc a corner's full swell reaches into the straight runs, px. The panel scales
 *  it with everything else; the tile passes it unscaled, so the swell dominates the small loop. */
export const CORNER_TAIL = 34;

/** Samples around the loop. Order eight around a panel-sized perimeter spans ~200px per wave, so
 *  this leaves better than twenty points per wave, smooth at one decimal of precision. */
const SAMPLES = 176;

/** How hard the working pose is chased, seconds to close ~63% of the remaining distance. */
const DEPTH_TAU = 0.28;

/** The style's worst-case displacement, px: every wave at crest, at full working depth. */
export function reachOf(style: EdgeStyle): number {
  const resting = style.waves.reduce((sum, wave) => sum + wave.amplitude, 0);
  return resting * (1 + style.depthBoost);
}

/** Ease a depth toward its target, frame-rate independent: the same fraction of the remaining
 *  distance closes per unit time whatever the frame spacing does. */
export function approachDepth(current: number, target: number, dtSeconds: number): number {
  if (dtSeconds <= 0) {
    return current;
  }
  return target + (current - target) * Math.exp(-dtSeconds / DEPTH_TAU);
}

interface Segment {
  readonly length: number;
  /** Point and outward normal at `fraction` of the way along, plus corner weight there. */
  readonly at: (fraction: number) => { x: number; y: number; nx: number; ny: number; cw: number };
}

/** The rounded rectangle `(0,0)..(w,h)` with radius `r`, as segments walked clockwise from the
 *  top-left arc's end. Corner weight is 1 on the arcs and falls off along the runs over the tail,
 *  so the swell is concentrated at the corners and the runs keep only their configured share. */
function segmentsOf(w: number, h: number, r: number, tail: number): readonly Segment[] {
  const fall = (distance: number): number =>
    distance >= tail ? 0 : 0.5 * (1 + Math.cos((Math.PI * distance) / tail));
  const run = (length: number, place: (along: number) => readonly [number, number], nx: number, ny: number): Segment => ({
    length,
    at: (fraction) => {
      const along = fraction * length;
      const [x, y] = place(along);
      return { x, y, nx, ny, cw: fall(Math.min(along, length - along)) };
    },
  });
  const arc = (cx: number, cy: number, from: number): Segment => ({
    length: (Math.PI * r) / 2,
    at: (fraction) => {
      const angle = from + (fraction * Math.PI) / 2;
      const nx = Math.cos(angle);
      const ny = Math.sin(angle);
      return { x: cx + r * nx, y: cy + r * ny, nx, ny, cw: 1 };
    },
  });
  return [
    run(w - 2 * r, (a) => [r + a, 0], 0, -1),
    arc(w - r, r, -Math.PI / 2),
    run(h - 2 * r, (a) => [w, r + a], 1, 0),
    arc(w - r, h - r, 0),
    run(w - 2 * r, (a) => [w - r - a, h], 0, 1),
    arc(r, h - r, Math.PI / 2),
    run(h - 2 * r, (a) => [0, h - r - a], -1, 0),
    arc(r, r, Math.PI),
  ];
}

/** A plain rounded rectangle path at `(x,y)..(x+w,y+h)`: the still edge, and the fallback for a
 *  box too small to carry the liquid (start-up, tests, a collapsed panel mid-mount). */
function roundedRect(x: number, y: number, w: number, h: number, r: number): string {
  const radius = Math.max(0, Math.min(r, w / 2, h / 2));
  const right = x + w;
  const bottom = y + h;
  const a = (dx: number, dy: number) => `A${radius} ${radius} 0 0 1 ${dx} ${dy}`;
  return (
    `M${x + radius} ${y}H${right - radius}${a(right, y + radius)}V${bottom - radius}` +
    `${a(right - radius, bottom)}H${x + radius}${a(x, bottom - radius)}V${y + radius}` +
    `${a(x + radius, y)}Z`
  );
}

/** The displacement at `loopFraction` of the way around, px, positive outward. Bounded by the
 *  reach: weights and the depth scale never exceed 1 and the crests never all align past it. */
function displacementAt(
  style: EdgeStyle,
  loopFraction: number,
  cornerWeight: number,
  seconds: number,
  depth: number,
): number {
  const weight = style.edgeShare + (1 - style.edgeShare) * cornerWeight;
  const scale = 1 + style.depthBoost * depth;
  let sum = 0;
  for (const wave of style.waves) {
    const angle =
      2 * Math.PI * wave.waves * loopFraction +
      wave.direction * ((2 * Math.PI) / wave.periodSeconds) * seconds +
      wave.phase;
    sum += wave.amplitude * Math.sin(angle);
  }
  return weight * scale * sum;
}

/** The rectangle one liquid loop is displaced around, placed wherever the caller draws, plus how
 *  far the spectrum swings on it. `amplitude` scales displacement and nothing else, so a miniature
 *  keeps a legible swing on a small rectangle instead of shrinking with its box, which is how the
 *  tile art re-tunes the motion for its size, as the mark tiles do (ADR-0036 addendum). */
export interface LoopFrame {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
  readonly radius: number;
  readonly amplitude: number;
  readonly tail: number;
}

/**
 * The loop's outline on an explicit frame at `seconds` on the clock and `depth` in [0, 1] of
 * the working pose, as an SVG path string usable as both a `path()` clip and a stroked `d`.
 */
export function loopPath(
  style: EdgeStyle,
  frame: LoopFrame,
  seconds: number,
  depth: number,
): string {
  const { x, y, width: w, height: h, radius } = frame;
  // A still style, or a box with no room for two arcs and a run between them, draws a plain rect.
  if (style.waves.length === 0 || w < 2 * radius + 16 || h < 2 * radius + 16) {
    return roundedRect(x, y, Math.max(0, w), Math.max(0, h), radius);
  }
  const segments = segmentsOf(w, h, radius, frame.tail);
  const total = segments.reduce((sum, segment) => sum + segment.length, 0);
  const parts: string[] = [];
  let index = 0;
  let start = 0;
  for (let i = 0; i < SAMPLES; i++) {
    const along = (i / SAMPLES) * total;
    while (along > start + (segments[index] as Segment).length) {
      start += (segments[index] as Segment).length;
      index += 1;
    }
    const segment = segments[index] as Segment;
    const point = segment.at((along - start) / segment.length);
    const d = displacementAt(style, i / SAMPLES, point.cw, seconds, depth) * frame.amplitude;
    const px = (point.x + point.nx * d + x).toFixed(1);
    const py = (point.y + point.ny * d + y).toFixed(1);
    parts.push(`${i === 0 ? "M" : "L"}${px} ${py}`);
  }
  return `${parts.join("")}Z`;
}

/** The panel's edge: `loopPath` on the uniform-inset frame the bleed wrapper implies, with the
 *  whole treatment (inset, radius, amplitude, tail) scaled together. */
export function edgePath(
  style: EdgeStyle,
  width: number,
  height: number,
  seconds: number,
  depth: number,
  scale = 1,
): string {
  const inset = BLEED * scale;
  return loopPath(
    style,
    {
      x: inset,
      y: inset,
      width: width - 2 * inset,
      height: height - 2 * inset,
      radius: CORNER_RADIUS * scale,
      amplitude: scale,
      tail: CORNER_TAIL * scale,
    },
    seconds,
    depth,
  );
}
