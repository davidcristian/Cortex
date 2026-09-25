import { useCallback, useLayoutEffect, useReducer, useRef } from "react";

import type { EdgeStyle } from "../edge/edges";
import { BLEED, approachDepth, edgePath } from "../edge/liquid";
import { useMarkClock } from "../mark/useMarkClock";

// The panel's liquid edge. Layers, back to front: the shadow, the glass slab with the animated clip,
// the glow strokes, the content, then the hairline. The box is measured into a ref, because
// `setState` in a per-render layout effect trips React's nested-update guard.

interface PanelEdgeProps {
  readonly style: EdgeStyle;
  /** A turn is running: the liquid deepens toward its working pose and the glow takes over. */
  readonly working: boolean;
  readonly animated: boolean;
  /** Keeps the glow gradient's SVG id unique per mount; ids are document-global. */
  readonly idPrefix: string;
}

/** The accent's own hues (theme/themes.ts ACTIVITY), as gradient stops. An SVG stroke cannot take
 *  the CSS `--accent` token, so they are restated here. */
const EMBER_STOPS = ["#8B5CF6", "#E24BC4", "#FF7A6B"] as const;

export function PanelEdge({ style, working, animated, idPrefix }: PanelEdgeProps) {
  const seconds = useMarkClock(animated);
  // The eased working depth, advanced by the frames themselves. Under reduced motion it jumps to
  // the target, since a still edge holds one shape per state.
  const pace = useRef({ seconds, depth: working ? 1 : 0 });
  const target = working ? 1 : 0;
  const depth = animated
    ? approachDepth(pace.current.depth, target, seconds - pace.current.seconds)
    : target;
  pace.current = { seconds, depth };

  const box = useRef<HTMLDivElement>(null!);
  const size = useRef({ width: 0, height: 0 });
  const [, bump] = useReducer((n: number) => n + 1, 0);
  const measure = useCallback(() => {
    const width = box.current.offsetWidth;
    const height = box.current.offsetHeight;
    if (size.current.width !== width || size.current.height !== height) {
      size.current = { width, height };
      bump();
    }
  }, []);
  useLayoutEffect(() => {
    // Measured once before first paint, so the edge never draws at zero size; after that the
    // observer drives it. jsdom has no layout, so under test the mount measurement is a stub and
    // the observer's deliveries are driven by hand (`src/test-setup.ts`).
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(box.current);
    return () => observer.disconnect();
  }, [measure]);

  const d = edgePath(style, size.current.width, size.current.height, seconds, depth);
  const ember = `${idPrefix}-ember`;
  const shade = `${idPrefix}-shade`;
  return (
    // The wrapper extends past the panel so the neutral outline sits on the panel's real edge and
    // the waves have room to swing outward. The inset is the geometry module's own constant.
    <div
      ref={box}
      className={`edge edge-${style.glow}${working ? " edge-working" : ""}`}
      style={{ inset: -BLEED }}
      aria-hidden="true"
    >
      {/* The shadow, cut out of the outline so the translucent glass does not darken over it. A
          filter on the wrapper would make it the glass's backdrop root, and the blur would see
          nothing behind the panel. */}
      <svg className="edge-shade">
        <defs>
          <filter id={shade} x="-20%" y="-20%" width="140%" height="160%">
            <feDropShadow dx="0" dy="26" stdDeviation="17" floodColor="#000" floodOpacity="0.38" />
            <feComposite operator="out" in2="SourceGraphic" />
          </filter>
        </defs>
        <path d={d} filter={`url(#${shade})`} />
      </svg>
      <div className="edge-glass" style={{ clipPath: `path("${d}")` }} />
      {style.glow === "none" ? null : (
        <svg className="edge-under">
          <defs>
            <linearGradient
              id={ember}
              gradientUnits="userSpaceOnUse"
              x1="0"
              y1="0"
              x2={size.current.width || 1}
              y2={size.current.height || 1}
            >
              {EMBER_STOPS.map((color, index) => (
                <stop
                  key={color}
                  offset={`${(index / (EMBER_STOPS.length - 1)) * 100}%`}
                  stopColor={color}
                />
              ))}
            </linearGradient>
          </defs>
          {style.glow === "settled" ? <path className="edge-glow-n" d={d} /> : null}
          <path className="edge-glow-a" d={d} stroke={`url(#${ember})`} />
        </svg>
      )}
      <svg className="edge-over">
        <path className="edge-hair" d={d} />
      </svg>
    </div>
  );
}
