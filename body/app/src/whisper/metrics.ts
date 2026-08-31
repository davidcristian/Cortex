import { pxOr } from "./front";

// What a whisper bubble measures about itself, and when that measurement stops being true
// (ADR-0037 decision 4). Every pose the clock writes is arithmetic over these numbers, so the
// arithmetic lives here beside the measurement rather than inside the frame loop: the loop poses
// the box from `boxFor` and so does a wrap change that arrives after the loop has stopped, and
// the two cannot drift apart.

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
 * The box the bubble needs while the condensation front stands at the end of a letter at
 * (`fx`, `fy`). On the first line the width walks with the front (plus room for the mist); past
 * the first wrap it is simply the final one. The height's target steps at a wrap, and the frame
 * loop's easing is what turns that step into a curve, while a re-pose after the loop has stopped
 * takes the same number at once.
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
 * Watch for the wrap width the letters were laid at ceasing to be the right one, and hand back
 * the removal. Only `maxW` is compared, because it is the only measurement a window change can
 * move: the paddings and the line box are px in the stylesheet, and the letters are re-laid for a
 * different wrap, not for a different rhythm.
 *
 * The trigger is the window's own `resize` (the idiom `overlay/usePanelMotion.ts` places the panel
 * on), which is complete for exactly as long as the panel's width stays viewport-derived, as
 * `.panel`'s `min(560px, 92vw)` keeps it. A `ResizeObserver` on the log would be the general
 * answer and is the wrong one here: the log's own height follows the posed bubble every frame of
 * every stream, so the callback would run per frame, and writing the letter DOM's width inside an
 * observation of an ancestor re-gathers at the same depth, which is the "loop completed with
 * undelivered notifications" error `overlay/panelWatch.ts` has already paid for once.
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
