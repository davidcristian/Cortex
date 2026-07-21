import type { EdgeStyle } from "../edge/edges";
import { edgePath } from "../edge/liquid";
import { useMarkClock } from "../mark/useMarkClock";

// A window edge as tile art (ADR-0036): the real liquid, scaled to a swatch, breathing live for
// the same reason the mark tiles do; these styles differ by how they move and what burns at the
// rim, so the choice is made by watching. The glow is drawn at rest even for the style whose
// glow only works (Reverie), because a swatch of four liquids has to show what each one is FOR;
// the note under the row says when the color actually appears.

/** The tile's box, ThemeMini's footprint, and the scale that puts the panel's 28px corner and
 *  its swell inside it. */
const WIDTH = 72;
const HEIGHT = 50;
const MINI_SCALE = 0.32;

interface EdgeMiniProps {
  readonly style: EdgeStyle;
  /** Keeps the gradient id unique per tile; ids are document-global. */
  readonly idPrefix: string;
  readonly animated: boolean;
}

/** The same accent stops PanelEdge restates; see the note there. */
const EMBER_STOPS = ["#8B5CF6", "#E24BC4", "#FF7A6B"] as const;

export function EdgeMini({ style, idPrefix, animated }: EdgeMiniProps) {
  const seconds = useMarkClock(animated);
  const d = edgePath(style, WIDTH, HEIGHT, seconds, 0, MINI_SCALE);
  const ember = `${idPrefix}-ember`;
  return (
    <svg
      className="edge-mini"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      width={WIDTH}
      height={HEIGHT}
      aria-hidden="true"
    >
      {style.glow === "none" ? null : (
        <defs>
          <linearGradient id={ember} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2={WIDTH} y2={HEIGHT}>
            {EMBER_STOPS.map((color, index) => (
              <stop key={color} offset={`${(index / (EMBER_STOPS.length - 1)) * 100}%`} stopColor={color} />
            ))}
          </linearGradient>
        </defs>
      )}
      <path className="edge-mini-glass" d={d} />
      {style.glow === "none" ? null : (
        <path className={`edge-mini-glow ${style.glow}`} d={d} stroke={`url(#${ember})`} />
      )}
      <path className="edge-mini-line" d={d} />
    </svg>
  );
}
