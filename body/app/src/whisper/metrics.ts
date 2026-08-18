import { pxOr } from "./front";

/** The mist's own box (`.mist i` in overlay.css) and the room the pose leaves around it. */
export const MIST_W = 24;
export const MIST_H = 13;
export const MIST_GAP = 2;

/** What the clock measured about the bubble; every pose is arithmetic over these. */
export interface Metrics {
  readonly padX: number;
  readonly padY: number;
  readonly line: number;
  /** The bubble's full wrap width (border box), the 82% cap resolved the way `max-width` is. */
  readonly maxW: number;
  readonly breathW: number;
  readonly breathH: number;
}

export function measure(bubble: HTMLElement): Metrics {
  const cs = getComputedStyle(bubble);
  const padX = pxOr(cs.paddingLeft, 15);
  const padY = pxOr(cs.paddingTop, 10);
  const line = pxOr(cs.lineHeight, 22.5);
  // The 0.82 restates `.bubble`'s `max-width: 82%` against the same content box; if the two
  // ever drift, the stylesheet's own max-width still clamps the posed width, so drift shows as
  // an early wrap rather than an overflow.
  const parent = bubble.parentElement;
  let content = 0;
  if (parent !== null) {
    const pcs = getComputedStyle(parent);
    content = parent.clientWidth - pxOr(pcs.paddingLeft, 0) - pxOr(pcs.paddingRight, 0);
  }
  const breathW = padX * 2 + MIST_W + 1;
  return {
    padX,
    padY,
    line,
    maxW: Math.max(breathW, Math.floor(content * 0.82) + padX * 2),
    breathW,
    breathH: padY * 2 + 22,
  };
}

/**
 * The box the bubble wants while the condensation front stands at the end of a letter at (`fx`,
 * `fy`).
 */
export function boxFor(
  m: Metrics,
  fx: number,
  fy: number,
): { readonly w: number; readonly h: number } {
  const lineOne = fy < m.padY + 5;
  return {
    w: Math.max(
      m.breathW,
      lineOne ? Math.min(m.maxW, fx + m.padX + MIST_W + MIST_GAP * 2) : m.maxW,
    ),
    h: Math.max(m.breathH, fy + m.line + m.padY),
  };
}

/**
 * Watch for the wrap width the letters were laid at ceasing to be the right one, and hand back the
 * removal.
 */
export function watchWrap(
  bubble: HTMLElement,
  from: Metrics,
  onChange: (m: Metrics) => void,
): () => void {
  let laidAt = from.maxW;
  const onResize = (): void => {
    const next = measure(bubble);
    if (next.maxW === laidAt) {
      return;
    }
    laidAt = next.maxW;
    onChange(next);
  };
  window.addEventListener("resize", onResize);
  return () => window.removeEventListener("resize", onResize);
}
