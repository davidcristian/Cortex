import { pxOr } from "./front";

// What a whisper bubble measures about itself, and when that measurement stops being true. The
// pose arithmetic lives here beside the measurement, so the frame loop and a later re-pose agree.

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
  // The 0.82 below restates `.bubble`'s `max-width: 82%` against the same content box. If the two
  // ever differ, the stylesheet's own max-width still clamps the posed width, so it shows up as an
  // early wrap rather than as an overflow.
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

/** Whether the bubble lays its letters right to left (`dir="auto"` read a Hebrew or Arabic first
 *  letter). Every pose below is in inline coordinates, measured from the bubble's start edge. */
export function rtlOf(bubble: HTMLElement): boolean {
  return getComputedStyle(bubble).direction === "rtl";
}

/** How far the inline end of letter `el` lies from the bubble's inline start edge. */
export function reachOf(m: Metrics, text: HTMLElement, el: HTMLElement, rtl: boolean): number {
  if (!rtl) {
    return el.offsetLeft + el.offsetWidth;
  }
  // A right-to-left text block wider than the posed box overflows past the box's left edge, so a
  // letter is measured from the text's right edge, which holds while the box grows.
  return m.padX + text.offsetLeft + text.offsetWidth - el.offsetLeft;
}

/** The farthest inline end among letters `0` to `seen - 1`: the box covers it. */
export interface Reach {
  at: number;
  seen: number;
}

/** Extend `r` over the letters up to index `i` and return the farthest end it has seen. In a
 *  line that mixes directions, a later letter can end nearer the start than an earlier one. */
export function reachTo(
  r: Reach,
  m: Metrics,
  text: HTMLElement,
  els: readonly HTMLElement[],
  i: number,
  rtl: boolean,
): number {
  for (; r.seen <= i; r.seen += 1) {
    r.at = Math.max(r.at, reachOf(m, text, els[r.seen]!, rtl));
  }
  return r.at;
}

/** The box the bubble needs while the condensation front stands at the end of a letter `fx`
 *  from the inline start edge and `fy` down. On the first line the width follows the front; past the first wrap it is the
 *  final width. The height's target steps at a wrap, and the frame loop eases it into a curve. */
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

/** Call `onChange` when the wrap width the letters were laid at is no longer the right one, and
 *  return the removal. It listens to the window's `resize` rather than observing the log, whose
 *  height follows the bubble every frame: an observer would run per frame and re-gather. */
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
