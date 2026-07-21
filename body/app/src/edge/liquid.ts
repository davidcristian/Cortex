// The dreaming edge's geometry (ADR-0036): a rounded rectangle sampled as one closed loop, each
// point displaced along its outward normal by the style's spectrum. Pure functions of numbers,
// like mark/bubble.ts: the component that renders this owns a clock and a box size, nothing here
// touches the DOM.
//
// The invariant this file owes the panel: the path NEVER leaves the given box. The neutral line
// is inset by the style's worst-case reach, so however deep the spectrum swings, the glass stays
// inside the panel's border box and the panel's layout, growth and shadow never learn the edge
// exists (ADR-0036 decision 5).

import type { EdgeStyle } from "./edges";

/** The panel's own corner radius (overlay.css `.panel`), which the neutral line carries. */
export const CORNER_RADIUS = 28;

/** How far past its arc a corner's full swell reaches into the straight runs, px. */
const CORNER_TAIL = 34;

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
 *  top-left arc's end. Corner weight is 1 on the arcs and falls off along the runs over the
 *  tail, so the swell belongs to the corners and the runs keep only their configured share. */
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

/**
 * The edge's outline for a `width` x `height` box at `seconds` on the clock and `depth` in
 * [0, 1] of the working pose, as an SVG path string usable as both a `path()` clip and a
 * stroked `d`. `scale` shrinks the whole treatment for a miniature (the tile art).
 */
export function edgePath(
  style: EdgeStyle,
  width: number,
  height: number,
  seconds: number,
  depth: number,
  scale = 1,
): string {
  const inset = reachOf(style) * scale;
  const radius = CORNER_RADIUS * scale;
  const w = width - 2 * inset;
  const h = height - 2 * inset;
  // A still style, or a box with no room for two arcs and a run between them: the plain rect.
  if (style.waves.length === 0 || w < 2 * radius + 16 || h < 2 * radius + 16) {
    return roundedRect(inset, inset, Math.max(0, w), Math.max(0, h), radius);
  }
  const segments = segmentsOf(w, h, radius, CORNER_TAIL * scale);
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
    const d = displacementAt(style, i / SAMPLES, point.cw, seconds, depth) * scale;
    const x = (point.x + point.nx * d + inset).toFixed(1);
    const y = (point.y + point.ny * d + inset).toFixed(1);
    parts.push(`${i === 0 ? "M" : "L"}${x} ${y}`);
  }
  return `${parts.join("")}Z`;
}
