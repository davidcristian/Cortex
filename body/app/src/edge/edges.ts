// The window's edge, as a plug-and-play registry (ADR-0036), the third of the appearance
// registries beside theme/themes.ts and mark/marks.ts: an edge style is a named set of numbers,
// and adding one to EDGES makes it pickable with no other code change. All geometry lives in
// liquid.ts; this file is only the numbers.
//
// The labels are a ladder of dream depth, Still to Trance, so the order of this registry IS the
// explanation of intensity and the tile row needs no caption (the naming language, ADR-0031
// addendum). `name` is the storage key the preference record holds (ADR-0032); keys are the
// lowercase labels from day one and are frozen the way the mark's are.

/** One wave of the edge's spectrum. `waves` is the spatial order around the loop and must be an
 *  integer of two or higher: integers are what close the loop without a seam, and order >= 2 is
 *  what holds the shape's centre still (the same invariant the mark pins). */
export interface EdgeWave {
  readonly waves: number;
  /** Peak displacement of this wave alone, px, at rest and full corner weight. */
  readonly amplitude: number;
  readonly periodSeconds: number;
  readonly direction: 1 | -1;
  readonly phase: number;
}

/** What rides the outline. `none` is bare glass and hairline; `settled` is neutral at rest and
 *  takes the accent while a turn runs; `ember` keeps a low accent lit at rest, the one written
 *  exception to color-is-activity (ADR-0036). */
export type EdgeGlow = "none" | "settled" | "ember";

/** The parameters that make one window edge. */
export interface EdgeStyle {
  readonly name: string;
  /** How the style is named in the picker. */
  readonly label: string;
  /** One-line description shown under the picker. */
  readonly note: string;
  readonly waves: readonly EdgeWave[];
  /** The share of the swell the straight runs keep; corners always take the whole of it. */
  readonly edgeShare: number;
  /** How much the amplitudes deepen at full working depth (a factor added to 1). */
  readonly depthBoost: number;
  readonly glow: EdgeGlow;
}

/** Today's crisp glass, holding perfectly still, as a real choice rather than an off switch. */
export const STILL: EdgeStyle = {
  name: "still",
  label: "Still",
  note: "Wide awake, the glass holding its edge exactly",
  waves: [],
  edgeShare: 0,
  depthBoost: 0,
  glow: "none",
};

/** Dreaming with clear eyes: the glass goes liquid and the color story stays exactly strict. */
export const LUCID: EdgeStyle = {
  name: "lucid",
  label: "Lucid",
  note: "Dreaming clearly, liquid in shape and strict about colour",
  waves: [
    { waves: 2, amplitude: 2.7, periodSeconds: 20.3, direction: 1, phase: 0.9 },
    { waves: 3, amplitude: 1.95, periodSeconds: 13.4, direction: -1, phase: 2.2 },
    { waves: 4, amplitude: 1.4, periodSeconds: 27.3, direction: 1, phase: 4.4 },
    { waves: 5, amplitude: 1.05, periodSeconds: 11.9, direction: -1, phase: 1.3 },
    { waves: 6, amplitude: 0.8, periodSeconds: 15.3, direction: 1, phase: 5.1 },
    { waves: 7, amplitude: 0.6, periodSeconds: 10.3, direction: 1, phase: 3.0 },
  ],
  edgeShare: 0.5,
  depthBoost: 0.38,
  glow: "none",
};

/** The one the user stopped at: Lucid's liquid with a smolder riding the rim. */
export const REVERIE: EdgeStyle = {
  ...LUCID,
  name: "reverie",
  label: "Reverie",
  note: "Adrift, with a glow that catches the accent while it works",
  glow: "settled",
};

/** Past reverie, under: a thicker spectrum, a touch quicker, and the ember never quite sleeps. */
export const TRANCE: EdgeStyle = {
  name: "trance",
  label: "Trance",
  note: "Deeper under, where the ember never quite goes out",
  waves: [
    { waves: 2, amplitude: 2.6, periodSeconds: 15.0, direction: 1, phase: 0.6 },
    { waves: 3, amplitude: 2.0, periodSeconds: 10.0, direction: -1, phase: 2.8 },
    { waves: 4, amplitude: 1.6, periodSeconds: 20.3, direction: 1, phase: 4.9 },
    { waves: 5, amplitude: 1.2, periodSeconds: 8.8, direction: -1, phase: 1.1 },
    { waves: 6, amplitude: 0.9, periodSeconds: 11.4, direction: 1, phase: 3.6 },
    { waves: 7, amplitude: 0.65, periodSeconds: 7.7, direction: 1, phase: 5.4 },
    { waves: 8, amplitude: 0.5, periodSeconds: 13.4, direction: -1, phase: 2.3 },
  ],
  edgeShare: 0.5,
  depthBoost: 0.27,
  glow: "ember",
};

/** The registry, in ladder order: the row of tiles reads Still to Trance and that order is the
 *  explanation. Plug-and-play: add an `EdgeStyle` here and it becomes pickable. */
export const EDGES: readonly EdgeStyle[] = [STILL, LUCID, REVERIE, TRANCE];

/** Reverie carries Lucid's spectrum on purpose (the glow is the whole difference), so the
 *  difference is data the tests can pin rather than a coincidence. */

/** Resolve the active edge: a known name wins, anything else falls back to the default, which is
 *  Lucid by the user's explicit call (ADR-0036): a fresh overlay breathes. */
export function resolveEdge(preference: string | null): EdgeStyle {
  if (preference !== null) {
    const chosen = EDGES.find((edge) => edge.name === preference);
    if (chosen !== undefined) {
      return chosen;
    }
  }
  return LUCID;
}
