// The pure half of the whispered streaming: the condensation front, and the token boxes the
// bubble lays out. Arithmetic over numbers and strings only; the clock is `useWhisperClock.ts`.

/** How many letters the condensation band spans: a letter clears over this much front travel. */
export const BAND_LETTERS = 9;

/** The time the front aims to trail arrivals by; velocity is backlog over this. */
export const CATCHUP_SECONDS = 0.35;

/** The front never moves slower than this while it has anywhere to go (letters per second). */
export const MIN_PACE = 20;

/** The front never moves faster than this, so a burst reads as flow rather than a jump. */
export const MAX_PACE = 150;

/** How fast the velocity eases toward its target (per second of gain). */
export const VELOCITY_GAIN = 6;

/** A run of non-whitespace longer than this is split into boxes the bubble can break between,
 *  so `overflow-wrap: anywhere` still works inside something like a streamed 64-char hash. */
export const CHUNK_LETTERS = 24;

export interface Front {
  /** The position, in letters from the reply's start; fractional on purpose. */
  readonly at: number;
  readonly velocity: number;
}

export const RESTING_FRONT: Front = { at: 0, velocity: 0 };

/** One frame of front travel toward `goal` letters, `dt` seconds after the last one. The front
 *  never moves backward: pulling it back would un-condense letters that already stand. */
export function advance(front: Front, goal: number, dt: number): Front {
  const backlog = goal - front.at;
  const target =
    backlog > 0 ? Math.min(MAX_PACE, Math.max(MIN_PACE, backlog / CATCHUP_SECONDS)) : 0;
  const velocity = front.velocity + (target - front.velocity) * Math.min(1, dt * VELOCITY_GAIN);
  return { at: Math.max(front.at, Math.min(goal, front.at + velocity * dt)), velocity };
}

/** Where the front is headed: the confirmed letters while streaming, and one whole band past the
 *  last letter once draining. A letter finishes only when the front is a full band beyond it, so
 *  without that overshoot the tail never sets. */
export function goalOf(letters: number, confirmed: number, draining: boolean): number {
  return draining ? letters + BAND_LETTERS : Math.min(confirmed, letters);
}

/** The band as a ramp: how condensed letter `index` is under a front at `at`, from 0 (mist) to 1
 *  (ink). Smoothstepped, so both ends of a letter's fade arrive without a corner. */
export function rampAt(at: number, index: number): number {
  const p = (at - index) / BAND_LETTERS;
  if (p <= 0) {
    return 0;
  }
  if (p >= 1) {
    return 1;
  }
  return p * p * (3 - 2 * p);
}

/** Exponential tracking toward a target: the box's and the mist's per-frame ease. It is
 *  frame-rate independent for a gain per second, and never jumps or overshoots. */
export function approach(value: number, target: number, dt: number, gain: number): number {
  return value + (target - value) * Math.min(1, dt * gain);
}

/** A CSS length like "22.475px", or `fallback` when the engine offers nothing usable (jsdom
 *  answers "" for everything). Values under 4 are rejected too: a unitless line-height would
 *  parse as its multiplier and pose the box a couple of pixels tall. */
export function pxOr(raw: string, fallback: number): number {
  const parsed = Number.parseFloat(raw);
  return Number.isFinite(parsed) && parsed >= 4 ? parsed : fallback;
}

export interface Token {
  readonly kind: "word" | "gap";
  readonly text: string;
}

/** The reply as the bubble lays it out: unbreakable word boxes and whitespace gaps kept as they
 *  are, since `pre-wrap` renders them. Splitting is by code point, so a surrogate pair never ends
 *  up half in one box, and appending only grows the last token, which keeps React's keys stable. */
export function tokenize(content: string): readonly Token[] {
  const tokens: Token[] = [];
  for (const run of content.split(/(\s+)/)) {
    if (run === "") {
      continue;
    }
    if (/^\s/.test(run)) {
      tokens.push({ kind: "gap", text: run });
      continue;
    }
    const points = [...run];
    for (let start = 0; start < points.length; start += CHUNK_LETTERS) {
      tokens.push({ kind: "word", text: points.slice(start, start + CHUNK_LETTERS).join("") });
    }
  }
  return tokens;
}

/** How many letter spans the tokens lay (gaps are text nodes, not letters). */
export function letterCountOf(tokens: readonly Token[]): number {
  let count = 0;
  for (const token of tokens) {
    if (token.kind === "word") {
      count += [...token.text].length;
    }
  }
  return count;
}

/** The letters the front may reveal while the turn still streams: everything up to the last
 *  completed word. A trailing word has no whitespace after it yet, so it can still grow and
 *  re-wrap; holding its letters at zero means only invisible letters ever move. */
export function confirmedOf(tokens: readonly Token[]): number {
  const last = tokens[tokens.length - 1];
  const total = letterCountOf(tokens);
  return last !== undefined && last.kind === "word" ? total - [...last.text].length : total;
}
