import type { LinkState, LinkStatus, TransportError } from "../bridge/types";

// The connection indicator's pure half (ADR-0011 addendum): what the overlay currently knows
// about the seam, how each observation changes it, and how that reads on screen. Kept out of
// React and out of the dot component so the honesty rules below are testable on their own.
//
// The two facts are deliberately separate. `state` is the last thing the brain *proved*
// (`LinkState` from the seam, plus the overlay's own `unknown` for "not asked yet"), and
// `probing` is whether an answer is on its way, which is the overlay's own fact and never the
// seam's. Composing them is what gives a reconnect its own reading without inventing a state
// the seam cannot report: the dot keeps the colour of what was last true and pulses while it
// finds out, so a blip never flashes green and a recovery never flashes red.

/** What the overlay knows about the brain link right now. */
export interface LinkView {
  /** The last proven state, or `"unknown"` before the first answer. */
  readonly state: LinkState | "unknown";
  /** The detail behind that state, for the tooltip; `""` when there is nothing to add. */
  readonly detail: string;
  /** Whether a probe is in flight (the overlay's own fact, not the brain's). */
  readonly probing: boolean;
}

/** Before anything has been asked: no claim, no probe. */
export const INITIAL_LINK: LinkView = { state: "unknown", detail: "", probing: false };

/** A probe went out: keep the last known state, and say an answer is coming. */
export function linkProbing(link: LinkView): LinkView {
  return { ...link, probing: true };
}

/** A probe answered: it replaces both facts, because it is the freshest thing known. */
export function linkObserved(status: LinkStatus): LinkView {
  return { state: status.state, detail: status.detail, probing: false };
}

/**
 * A probe could not be delivered (the IPC itself rejected, not the brain). That says nothing
 * about the brain, so the last known state stands and only the in-flight flag clears. The
 * alternative, calling the brain down because the body's own plumbing failed, would point the
 * user at the wrong machine.
 */
export function linkProbeEnded(link: LinkView): LinkView {
  return link.probing ? { ...link, probing: false } : link;
}

/**
 * The brain streamed a turn event, which proves it is serving without a probe. A stale failure
 * detail would read as a caption under a green dot, so it is dropped; a detail earned while
 * already ready (the brain naming itself) is kept, and an unchanged view is returned as-is so
 * a streaming turn does not re-render the header on every token.
 */
export function linkServing(link: LinkView): LinkView {
  return link.state === "ready" ? link : { ...link, state: "ready", detail: "" };
}

/**
 * A turn failed at the transport, which proves the same things a probe failure does and is
 * classified the same way (`body_core::link`): unreachable is `down`, an answered-but-wrong
 * call (a non-OK status, an unreadable reply) is `degraded`.
 */
export function linkFailed(link: LinkView, error: TransportError): LinkView {
  return {
    ...link,
    state: error.kind === "connection" ? "down" : "degraded",
    detail: error.message,
  };
}

/** How the indicator reads: a colour tone, whether it is mid-check, and the label it announces. */
export interface LinkReading {
  readonly tone: "ok" | "warn" | "bad" | "idle";
  readonly busy: boolean;
  readonly label: string;
}

const TONES: Record<LinkView["state"], LinkReading["tone"]> = {
  ready: "ok",
  degraded: "warn",
  down: "bad",
  unknown: "idle",
};

/** Appends the detail to a label, when there is one worth showing. */
function withDetail(label: string, detail: string): string {
  return detail === "" ? label : `${label}: ${detail}`;
}

/** Renders a link view as the dot's tone and its human label (the tooltip + the a11y name). */
export function describeLink(link: LinkView): LinkReading {
  const tone = TONES[link.state];
  // A probe while already ready is a routine refresh: it must not make a healthy link look
  // busy. Any other probe is the interesting one, and it keeps the last known colour.
  const busy = link.probing && link.state !== "ready";
  if (busy) {
    return { tone, busy, label: "Checking the connection to the brain" };
  }
  switch (link.state) {
    case "ready":
      return { tone, busy, label: withDetail("Brain ready", link.detail) };
    case "degraded":
      return { tone, busy, label: withDetail("The brain is not serving", link.detail) };
    case "down":
      return { tone, busy, label: withDetail("Cannot reach the brain", link.detail) };
    case "unknown":
      return { tone, busy, label: "The brain connection has not been checked yet" };
  }
}
