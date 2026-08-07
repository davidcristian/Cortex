import { type RefObject, useEffect, useRef, useState } from "react";

import { MORPHING_ATTRIBUTE, MORPH_END_EVENT, MORPH_START_EVENT } from "../overlay/morph";
import {
  BAND_LETTERS,
  type Front,
  RESTING_FRONT,
  advance,
  approach,
  goalOf,
  pxOr,
  rampAt,
} from "./front";

// The whisper's frame clock (ADR-0037), `useMarkClock`'s shape put to work: one rAF loop that
// writes the letter ramps, the mist's glide and the bubble's posed box as inline styles, never
// through React. Its only `setState` is the two phase transitions (breath to talking, talking to
// settled), which is the lesson ADR-0036 recorded about rAF clocks beside React: per-frame state
// is a ref, and what the loop needs from the latest render it reads out of a ref assigned during
// that render, so the loop subscribes to nothing and never restarts mid-reply.

export type WhisperPhase = "breath" | "talking" | "settled";

/** How fast the posed box chases the front (per second of gain). */
const BOX_GAIN = 10;
/** The mist eases a little quicker than the box, so it reads as leading, not dragged. */
const MIST_GAIN = 12;
/** How far the front must travel before the breath becomes speech. */
const TALK_THRESHOLD = 0.05;
/** The mist's own box (`.mist i` in overlay.css) and the room the pose leaves around it. */
const MIST_W = 24;
const MIST_H = 13;
const MIST_GAP = 2;
/** How deep the band's blur goes at the mist end of a letter's ramp. */
const BLUR_PX = 4;
/** A clock tick is capped here so a background tab's resumed frame cannot teleport the front. */
const MAX_TICK_SECONDS = 0.05;
/** A height change worth reporting to the tail pin; the box eases in sub-pixel steps below it. */
const GROWTH_NOTICE_PX = 0.5;

export interface WhisperRefs {
  readonly bubble: RefObject<HTMLElement | null>;
  readonly text: RefObject<HTMLElement | null>;
  readonly mist: RefObject<HTMLElement | null>;
}

export interface WhisperFacts {
  readonly streaming: boolean;
  /** Letter spans laid in the text (the `.ch` count). */
  readonly letters: number;
  /** Letters the front may reveal while streaming (`confirmedOf`). */
  readonly confirmed: number;
  /** False under reduced motion: no frames are scheduled at all, the mark's standard. */
  readonly animated: boolean;
  /** Fired when the posed box grows, so the history's tail pin can follow the drain. */
  readonly onGrow: () => void;
}

/** What the clock measured once at mount; every pose is arithmetic over these. */
interface Metrics {
  readonly padX: number;
  readonly padY: number;
  readonly line: number;
  /** The bubble's full wrap width (border box), the 82% cap resolved the way `max-width` is. */
  readonly maxW: number;
  readonly breathW: number;
  readonly breathH: number;
}

/** The per-frame mutable world, deliberately a ref and never state. */
interface World {
  front: Front;
  lo: number;
  letters: HTMLElement[];
  collected: number;
  talking: boolean;
  w: number;
  h: number;
  mx: number;
  my: number;
}

function measure(bubble: HTMLElement): Metrics {
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
    content =
      parent.clientWidth - pxOr(pcs.paddingLeft, 0) - pxOr(pcs.paddingRight, 0);
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

/** One letter's paint under the band: fractional opacity and blur, pinned at "1" once done
 *  because the `.ch` class holds unreached letters at zero and clearing the inline style would
 *  hand a finished letter back to it. */
function paint(el: HTMLElement, q: number): void {
  if (q >= 1) {
    el.style.opacity = "1";
    el.style.filter = "";
    return;
  }
  el.style.opacity = q.toFixed(3);
  el.style.filter = `blur(${((1 - q) * BLUR_PX).toFixed(2)}px)`;
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

/**
 * Drive one live whisper. Returns the phase for the bubble's state class; under
 * `animated: false` it schedules nothing and derives the phase from the message alone (the
 * stylesheet reveals letters as they arrive, and the CSS breath floor holds the waiting pill).
 */
export function useWhisperClock(refs: WhisperRefs, facts: WhisperFacts): WhisperPhase {
  const [phase, setPhase] = useState<WhisperPhase>("breath");
  const live = useRef(facts);
  live.current = facts;
  const world = useRef<World>({
    front: RESTING_FRONT,
    lo: 0,
    letters: [],
    collected: -1,
    talking: false,
    w: 0,
    h: 0,
    mx: 0,
    my: 0,
  });

  const { bubble: bubbleRef, text: textRef, mist: mistRef } = refs;
  const animated = facts.animated;
  useEffect(() => {
    const bubble = bubbleRef.current;
    const text = textRef.current;
    const mist = mistRef.current;
    if (!animated || bubble === null || text === null || mist === null) {
      return undefined;
    }
    const m = measure(bubble);
    const s = world.current;
    // The letter DOM lays out ONCE, at the final wrap width, so letter positions never change
    // after they are laid: only the posed box's edge moves (ADR-0037 decision 4).
    text.style.width = `${Math.max(0, m.maxW - m.padX * 2)}px`;
    // The waiting pose: the box drawn around the mist, and a front that starts a whole band
    // past whatever is already confirmed, so a bubble remounted mid-stream (maximize onto a
    // running turn) shows the words it already has, fully condensed, instead of replaying
    // them. A fresh turn starts at zero, or the first arrivals would pop in as ink.
    const confirmed = live.current.confirmed;
    s.front = { at: confirmed > 0 ? confirmed + BAND_LETTERS : 0, velocity: 0 };
    s.w = m.breathW;
    s.h = m.breathH;
    s.mx = m.padX;
    s.my = m.breathH / 2 - MIST_H / 2;
    bubble.style.width = `${s.w.toFixed(1)}px`;
    bubble.style.height = `${s.h.toFixed(1)}px`;
    mist.style.transform = `translate(${s.mx.toFixed(1)}px, ${s.my.toFixed(1)}px)`;

    const tick = (dt: number): boolean => {
      const f = live.current;
      const draining = !f.streaming;
      if (s.collected !== f.letters) {
        s.letters = Array.from(text.querySelectorAll<HTMLElement>(".ch"));
        s.collected = f.letters;
      }
      const els = s.letters;
      if (els.length === 0) {
        // Nothing to condense. A stopped turn with no reply settles at once; a breath waits.
        if (draining) {
          setPhase("settled");
          return true;
        }
        return false;
      }
      s.front = advance(s.front, goalOf(els.length, f.confirmed, draining), dt);
      if (!s.talking && s.front.at > TALK_THRESHOLD) {
        s.talking = true;
        setPhase("talking");
      }
      for (let i = s.lo; i < els.length; i += 1) {
        const q = rampAt(s.front.at, i);
        if (q <= 0) {
          break;
        }
        paint(els[i]!, q);
        // The ramp falls with the index, so a fully condensed letter can only be the first
        // unfinished one: advancing here keeps the loop bounded to the band.
        if (q >= 1) {
          s.lo += 1;
        }
      }
      if (!s.talking) {
        return false;
      }
      const fi = clamp(Math.floor(s.front.at), 0, els.length - 1);
      const el = els[fi]!;
      const fx = el.offsetLeft + el.offsetWidth;
      const fy = el.offsetTop;
      // The box tracks the front: on the first line the width walks with it (plus room for the
      // mist); past the first wrap it is simply the final one. The height's target steps at a
      // wrap, and the easing is what turns that step into a curve.
      const lineOne = fy < m.padY + 5;
      const finished = draining && s.lo >= els.length;
      const tW = Math.max(
        m.breathW,
        lineOne ? Math.min(m.maxW, fx + m.padX + MIST_W + MIST_GAP * 2) : m.maxW,
      );
      const tH = Math.max(m.breathH, fy + m.line + m.padY);
      // The bubble owns its height for the length of the stream, and says so in the panel's own
      // roll contract (`overlay/morph.ts`): placements defer while the attribute stands, so the
      // panel's auto height follows the dev machine frame by frame instead of replaying it from a
      // render-old measurement, which snapped the top edge backwards on every token of a reply
      // that outgrew the chat floor (traced in headless Chromium at 660x1000: eight reversals of
      // up to 6.6px in one reply; zero once the bubble announced its roll). The value is the
      // height being eased to, which is what lets the panel take its bottom edge along when a
      // landing line would push it past the ceiling, written the way the box below is written so
      // both sides of the contract hold one number rather than two roundings of it. Rounded to a
      // whole pixel it sat exactly 0.5px under the height the box stands on at all five lines of
      // a reply traced at 900x1000, and a summon landing inside the roll then pinned the panel
      // 0.25px off the centre it aimed for and kept that edge for the session.
      const rolling = tH.toFixed(1);
      if (bubble.getAttribute(MORPHING_ATTRIBUTE) !== rolling) {
        const announced = bubble.hasAttribute(MORPHING_ATTRIBUTE);
        bubble.setAttribute(MORPHING_ATTRIBUTE, rolling);
        if (!announced) {
          bubble.dispatchEvent(new CustomEvent(MORPH_START_EVENT, { bubbles: true }));
        }
      }
      s.w = finished ? tW : approach(s.w, tW, dt, BOX_GAIN);
      const h = finished ? tH : approach(s.h, tH, dt, BOX_GAIN);
      const grown = h - s.h;
      s.h = h;
      bubble.style.width = `${s.w.toFixed(1)}px`;
      bubble.style.height = `${s.h.toFixed(1)}px`;
      // Clamped into the box, so the blob hugs an edge rather than leaving the bubble.
      const gx = clamp(fx + MIST_GAP, m.padX, s.w - MIST_W - 6);
      const gy = clamp(fy + m.line / 2 - MIST_H / 2, 4, s.h - MIST_H - 4);
      s.mx = approach(s.mx, gx, dt, MIST_GAIN);
      s.my = approach(s.my, gy, dt, MIST_GAIN);
      mist.style.transform = `translate(${s.mx.toFixed(1)}px, ${s.my.toFixed(1)}px)`;
      if (grown >= GROWTH_NOTICE_PX) {
        f.onGrow();
      }
      // The settle waits for the mist. The drain sprints the front and the blob trails it on
      // its own ease, so stopping the clock the instant the last letter cleared froze the glide
      // mid-line and the evaporation played a dozen letters short of the reply's end (the user
      // caught the smudge in a screenshot). This coda runs the loop the few frames it takes the
      // mist to reach the last word, and the reply ends where it says it does.
      if (finished && Math.abs(gx - s.mx) < 1 && Math.abs(gy - s.my) < 1) {
        bubble.removeAttribute(MORPHING_ATTRIBUTE);
        bubble.dispatchEvent(new CustomEvent(MORPH_END_EVENT, { bubbles: true }));
        setPhase("settled");
        return true;
      }
      return false;
    };

    let last: number | null = null;
    let frame = requestAnimationFrame(function step(now: number) {
      last ??= now;
      const dt = Math.min(MAX_TICK_SECONDS, (now - last) / 1000);
      last = now;
      if (!tick(dt)) {
        frame = requestAnimationFrame(step);
      }
    });
    return () => {
      cancelAnimationFrame(frame);
      // A bubble unmounted mid-stream (a chat switch under a running turn) hands the height
      // back explicitly, or the panel would keep deferring to a roll whose section is gone.
      if (bubble.hasAttribute(MORPHING_ATTRIBUTE)) {
        bubble.removeAttribute(MORPHING_ATTRIBUTE);
        bubble.dispatchEvent(new CustomEvent(MORPH_END_EVENT, { bubbles: true }));
      }
    };
  }, [animated, bubbleRef, textRef, mistRef]);

  if (!animated) {
    return facts.streaming ? (facts.letters > 0 ? "talking" : "breath") : "settled";
  }
  return phase;
}
