// Geometry for the bubble mark (design/overlay-ux.md §4). A soap bubble is a circle whose radius
// is modulated by low-order sine harmonics: the outline warps the way surface tension moves, while
// the centroid and the mean radius hold still, which is what keeps the corner anchor from
// wandering (every harmonic starts at n=2; an n=1 term would translate the whole shape). Paths are
// recomputed per frame from an elapsed-seconds clock. Nothing here touches the DOM.

/** How a harmonic's amplitude behaves over time: constant, or a crest that decays on a cadence. */
export type Envelope = "steady" | "ping";

/** Seconds between ping crests, and how fast one crest dies away. */
const PING_CADENCE_S = 3.4;
const PING_DECAY = 1.6;

const TAU = Math.PI * 2;

/** One surface mode: `waves` bulges per revolution, travelling once around every `periodSeconds`. */
export interface Harmonic {
  readonly waves: number;
  /** Peak radius deviation, as a fraction of the lobe radius. */
  readonly amplitude: number;
  readonly periodSeconds: number;
  readonly direction: 1 | -1;
  readonly envelope: Envelope;
}

/** A lobe's slow swing about an anchor, so a cluster can jostle without its centroid moving. */
export interface Orbit {
  readonly cx: number;
  readonly cy: number;
  readonly degrees: number;
  readonly periodSeconds: number;
}

/** One bubble in a mark. Marks are single-lobe except the foam cluster. */
export interface Lobe {
  readonly cx: number;
  readonly cy: number;
  readonly r: number;
  readonly harmonics: readonly Harmonic[];
  readonly orbit: Orbit;
}

/** Where a lobe sits at one instant: its center after the orbit swing. */
export interface PlacedLobe {
  readonly cx: number;
  readonly cy: number;
  readonly r: number;
}

/** A specular reflection: light source fixed, so it never rotates with the film. */
export interface Highlight {
  readonly cx: number;
  readonly cy: number;
  readonly rx: number;
  readonly ry: number;
  readonly degrees: number;
}

/** The amplitude multiplier for `envelope` at `seconds`: 1 while steady, decaying after a crest. */
export function envelopeAt(envelope: Envelope, seconds: number): number {
  if (envelope === "steady") {
    return 1;
  }
  return Math.exp(-PING_DECAY * (seconds % PING_CADENCE_S));
}

/** Place a lobe at `seconds`: a zero-degree orbit (every single-lobe mark) is the identity. */
export function lobeAt(lobe: Lobe, seconds: number): PlacedLobe {
  const swing = (lobe.orbit.degrees * Math.PI) / 180;
  const angle = swing * Math.sin((TAU * seconds) / lobe.orbit.periodSeconds);
  const dx = lobe.cx - lobe.orbit.cx;
  const dy = lobe.cy - lobe.orbit.cy;
  return {
    cx: lobe.orbit.cx + dx * Math.cos(angle) - dy * Math.sin(angle),
    cy: lobe.orbit.cy + dx * Math.sin(angle) + dy * Math.cos(angle),
    r: lobe.r,
  };
}

/** SVG path for a lobe's outline at `seconds`, sampled as a fine closed polyline. */
export function lobePath(lobe: Lobe, seconds: number, samples = 120): string {
  const placed = lobeAt(lobe, seconds);
  const steps = Array.from({ length: samples }, (_, index) => {
    const theta = (index / samples) * TAU;
    let radius = placed.r;
    for (const harmonic of lobe.harmonics) {
      const phase = harmonic.direction * harmonic.waves * TAU * (seconds / harmonic.periodSeconds);
      const amplitude = harmonic.amplitude * envelopeAt(harmonic.envelope, seconds);
      radius += amplitude * placed.r * Math.sin(harmonic.waves * theta + phase);
    }
    const x = placed.cx + radius * Math.cos(theta);
    const y = placed.cy + radius * Math.sin(theta);
    return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
  });
  return `${steps.join(" ")} Z`;
}

/** The two reflections of a fixed upper-left light: a soft wash and the hard specular dot. */
export function highlightsOf(placed: PlacedLobe): readonly [Highlight, Highlight] {
  return [
    {
      cx: placed.cx - placed.r * 0.42,
      cy: placed.cy - placed.r * 0.46,
      rx: placed.r * 0.4,
      ry: placed.r * 0.25,
      degrees: -30,
    },
    {
      cx: placed.cx - placed.r * 0.5,
      cy: placed.cy - placed.r * 0.54,
      rx: placed.r * 0.1,
      ry: placed.r * 0.062,
      degrees: -28,
    },
  ];
}

/** The bright crescent light throws on the far side of the film, opposite the highlight. */
export function causticPath(placed: PlacedLobe): string {
  const radius = placed.r * 0.78;
  const from = 0.35;
  const to = 1.5;
  const x0 = placed.cx + radius * Math.cos(from);
  const y0 = placed.cy + radius * Math.sin(from);
  const x1 = placed.cx + radius * Math.cos(to);
  const y1 = placed.cy + radius * Math.sin(to);
  const arc = `A ${radius.toFixed(2)} ${radius.toFixed(2)} 0 0 1`;
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} ${arc} ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}
