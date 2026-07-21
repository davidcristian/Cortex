import type { EdgeStyle } from "../edge/edges";
import { CORNER_TAIL, type LoopFrame, loopPath } from "../edge/liquid";
import { STILL_SECONDS, useMarkClock } from "../mark/useMarkClock";

// The Dream row's tile art (ADR-0036 addendum): a portrait, not a scale model. Each tile is the
// same miniature window the theme tiles draw (title, a reply, the composer), except its outline
// is the liquid. The first cut drew the real edge at a third of its size and the maintainer called
// the row ugly, with reason: honesty at that scale shrinks the bleed into dead margin and the
// waves into a nervous line. So the motion is re-tuned for the medium instead, the way the mark
// tiles are: a small pane, the amplitude nearly whole.

const WIDTH = 72;
const HEIGHT = 50;

/** The portrait's pane: where the liquid breathes inside the tile. The tail is left unscaled on
 *  purpose, so the corners' swell owns the whole little loop. */
const FRAME: LoopFrame = { x: 13, y: 9, width: 46, height: 32, radius: 7, amplitude: 0.85, tail: CORNER_TAIL };

/** Reverie's tile cycles between its two states on this period, seconds. Frozen in its accent
 *  the tile read as "a lighter Trance" (the maintainer's words), when the style IS the change:
 *  neutral at rest, accent while a turn runs. The cycle is the portrait of that. */
const BREATHE_S = 7;

/** Phase picked so the frozen pose (`STILL_SECONDS`) lands exactly mid-blend: a reduced-motion
 *  tile shows both truths at once instead of only one of them. */
const BREATHE_PHASE = Math.PI / 2 - (2 * Math.PI * STILL_SECONDS) / BREATHE_S;

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
  const d = loopPath(style, FRAME, seconds, 0);
  const ember = `${idPrefix}-ember`;
  const blend =
    style.glow === "settled"
      ? 0.5 * (1 - Math.cos((2 * Math.PI * seconds) / BREATHE_S + BREATHE_PHASE))
      : 1;
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
      {/* No ground of its own: the tile IS the ground the little window floats on. Painting one
          put a second surface inside the card and read as a panel stuck onto the swatch. The
          theme tiles below do carry one, because there the ground is the thing being chosen. */}
      <path className="edge-mini-glass" d={d} />
      {/* Reverie's resting smolder, neutral, handing over to the accent as the blend rises; the
          opacities are inline because they move every frame. */}
      {style.glow === "settled" ? (
        <path className="edge-mini-glow rest" d={d} style={{ opacity: 0.4 * (1 - blend) }} />
      ) : null}
      {style.glow === "none" ? null : (
        <path
          className={`edge-mini-glow ${style.glow}`}
          d={d}
          stroke={`url(#${ember})`}
          style={style.glow === "settled" ? { opacity: 0.5 * blend } : undefined}
        />
      )}
      <path className="edge-mini-line" d={d} />
      {/* The innards the theme tiles draw: title, a reply, the composer. */}
      <rect className="edge-mini-bar title" x="19" y="15" width="15" height="2.6" rx="1.3" />
      <rect className="edge-mini-bar msg" x="19" y="21" width="24" height="2.6" rx="1.3" />
      <rect className="edge-mini-pill" x="19" y="29" width="34" height="5.4" rx="2.7" />
    </svg>
  );
}
