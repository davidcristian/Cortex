import { useCallback, useLayoutEffect, useReducer, useRef } from "react";

import type { EdgeStyle } from "../edge/edges";
import { approachDepth, edgePath } from "../edge/liquid";
import { useMarkClock } from "../mark/useMarkClock";

// The panel's dreaming edge (ADR-0036). Layers, back to front: the glass slab wearing the
// animated clip, the blurred glow strokes, then the panel's content (`.views`, z-indexed above
// by overlay.css), then the crisp hairline. The slab is the ONLY thing the per-frame clip
// touches and it holds no text, which is what keeps the type as sharp as the still panel's; the
// glow lives under the content so nothing soft can cross a glyph (decision 6).
//
// The whole component re-renders per frame on the mark's own clock while the panel around it
// does not, the same split that keeps the bubble cheap. The box is measured once before first
// paint and re-measured only when it actually resizes (ResizeObserver), with the measurement in
// a ref the clock's renders read. It is NOT re-read via setState in a per-render layout effect:
// that shape trips React's nested-update guard once a clock renders every frame (measured in the
// dev overlay, which went down inside two seconds), and jsdom's driven frames never run long
// enough to catch it.

interface PanelEdgeProps {
  readonly style: EdgeStyle;
  /** A turn is running: the liquid deepens toward its working pose and the glow takes over. */
  readonly working: boolean;
  readonly animated: boolean;
  /** Keeps the glow gradient's SVG id unique per mount; ids are document-global. */
  readonly idPrefix: string;
}

/** The accent's own hues (theme/themes.ts ACTIVITY), as gradient stops: an SVG stroke cannot
 *  wear the CSS `--accent` token, so the stops are restated here the way the mark restates the
 *  palette. */
const EMBER_STOPS = ["#8B5CF6", "#E24BC4", "#FF7A6B"] as const;

export function PanelEdge({ style, working, animated, idPrefix }: PanelEdgeProps) {
  const seconds = useMarkClock(animated);
  // The eased working depth, advanced by the frames themselves so the deepening is a movement.
  // Not animating (reduced motion) snaps it: a still edge holds one pose per state, exactly.
  const pace = useRef({ seconds, depth: working ? 1 : 0 });
  const target = working ? 1 : 0;
  const depth = animated
    ? approachDepth(pace.current.depth, target, seconds - pace.current.seconds)
    : target;
  pace.current = { seconds, depth };

  // Mounted with the component, so the ref is always set by the time anything reads it.
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
    // Once before first paint, so the edge never shows a zero-size pose; after that the observer
    // owns it. The test DOM has no ResizeObserver and no layout either, so there the one mount
    // measurement is the whole story.
    measure();
    if (typeof ResizeObserver === "undefined") {
      return undefined;
    }
    const observer = new ResizeObserver(measure);
    observer.observe(box.current);
    return () => observer.disconnect();
  }, [measure]);

  const d = edgePath(style, size.current.width, size.current.height, seconds, depth);
  const ember = `${idPrefix}-ember`;
  return (
    <div
      ref={box}
      className={`edge edge-${style.glow}${working ? " edge-working" : ""}`}
      aria-hidden="true"
    >
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
