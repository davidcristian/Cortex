import { type RefObject, useEffect, useRef, useState } from "react";

import { MORPHING_ATTRIBUTE, MORPH_END_EVENT, MORPH_START_EVENT } from "../overlay/morph";
import {
  BAND_LETTERS,
  type Front,
  RESTING_FRONT,
  advance,
  approach,
  goalOf,
  rampAt,
} from "./front";
import { MIST_GAP, MIST_H, MIST_W, type Metrics, boxFor, measure, watchWrap } from "./metrics";

// The whisper's frame clock: one rAF loop that writes the letter ramps, the mist's glide and the
// bubble's posed box as inline styles, never through React. Per-frame state is a ref and what the
// loop needs from a render is read out of a ref, so the loop never restarts mid-reply.

export type WhisperPhase = "breath" | "talking" | "settled";

/** How fast the posed box chases the front (per second of gain). */
const BOX_GAIN = 10;
/** The mist eases a little quicker than the box, so it reads as leading rather than dragged. */
const MIST_GAIN = 12;
/** How far the front must travel before the breath becomes speech. */
const TALK_THRESHOLD = 0.05;
/** How deep the band's blur goes at the mist end of a letter's ramp. */
const BLUR_PX = 4;
/** A clock tick is capped here, so the first frame after a background tab resumes cannot jump
 *  the front far forward in one step. */
const MAX_TICK_SECONDS = 0.05;
/** A height change worth reporting, so the history can follow the tail; the box eases in
 *  sub-pixel steps below this. */
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
  /** Fired when the posed box grows, so the history can follow the tail through the drain. */
  readonly onGrow: () => void;
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

/** One letter's paint under the band: fractional opacity and blur, held at "1" once done. The
 *  `.ch` class keeps unreached letters at zero, so clearing the inline style would hand a
 *  finished letter back to it. */
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

/** Drive one live whisper and return the phase for the bubble's state class. With
 *  `animated: false` it schedules nothing and derives the phase from the message alone. */
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
    let m = measure(bubble);
    const s = world.current;
    // The letter DOM lays out at the measured wrap width, so letter positions hold for as long as
    // that width does and only the posed box's edge moves. A window that changes size re-lays them.
    const layOut = (): void => {
      text.style.width = `${Math.max(0, m.maxW - m.padX * 2)}px`;
    };
    layOut();
    // The waiting pose. The front starts a whole band past whatever is already confirmed, so a
    // bubble remounted mid-stream shows the words it already has, fully condensed, instead of
    // replaying them. A fresh turn starts at zero, or the first arrivals would appear as ink.
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
        // The ramp falls with the index, so a finished letter can only be the first unfinished
        // one: advancing here keeps the loop inside the band.
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
      const finished = draining && s.lo >= els.length;
      const { w: tW, h: tH } = boxFor(m, fx, fy);
      // The bubble owns its height while the stream runs and says so through the panel's roll
      // attribute, so the panel follows the box frame by frame. The value is kept to a tenth of a
      // pixel, not a whole one; docs/readings/panel-motion.md has the measurements.
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
      const gx = clamp(fx + MIST_GAP, m.padX, s.w - MIST_W - 6);
      const gy = clamp(fy + m.line / 2 - MIST_H / 2, 4, s.h - MIST_H - 4);
      s.mx = approach(s.mx, gx, dt, MIST_GAIN);
      s.my = approach(s.my, gy, dt, MIST_GAIN);
      mist.style.transform = `translate(${s.mx.toFixed(1)}px, ${s.my.toFixed(1)}px)`;
      if (grown >= GROWTH_NOTICE_PX) {
        f.onGrow();
      }
      // The settle waits for the mist. The drain moves the front quickly and the mist trails it on
      // its own ease, so stopping the clock when the last letter cleared froze the glide mid-line
      // and ended the evaporation a dozen letters short of the reply.
      if (finished && Math.abs(gx - s.mx) < 1 && Math.abs(gy - s.my) < 1) {
        bubble.removeAttribute(MORPHING_ATTRIBUTE);
        bubble.dispatchEvent(new CustomEvent(MORPH_END_EVENT, { bubbles: true }));
        setPhase("settled");
        return true;
      }
      return false;
    };

    // A bubble whose loop has stopped keeps the px box the loop left it with, and nothing else in
    // the overlay revisits it, so a re-wrap has to pose it here. It poses at once rather than
    // easing: the window's own resize is the motion, and an easing box would only trail the drag.
    const repose = (): void => {
      const tail = s.letters[s.letters.length - 1];
      if (tail === undefined) {
        // A turn that stopped before its first word settled at the breath pill, which is the
        // paddings and the mist, and a window change moves neither.
        return;
      }
      const box = boxFor(m, tail.offsetLeft + tail.offsetWidth, tail.offsetTop);
      s.w = box.w;
      s.h = box.h;
      bubble.style.width = `${s.w.toFixed(1)}px`;
      bubble.style.height = `${s.h.toFixed(1)}px`;
      // A re-wrap moves the tail of the log; this puts back a reader who was reading it.
      live.current.onGrow();
    };

    let stopped = false;
    let last: number | null = null;
    let frame = requestAnimationFrame(function step(now: number) {
      last ??= now;
      const dt = Math.min(MAX_TICK_SECONDS, (now - last) / 1000);
      last = now;
      if (tick(dt)) {
        stopped = true;
      } else {
        frame = requestAnimationFrame(step);
      }
    });
    const unwatch = watchWrap(bubble, m, (next: Metrics) => {
      m = next;
      layOut();
      if (stopped) {
        repose();
      }
    });
    return () => {
      unwatch();
      cancelAnimationFrame(frame);
      // A bubble unmounted mid-stream, on a chat switch under a running turn, hands the height
      // back, or the panel would keep deferring to a roll whose section is gone.
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
