import type { LinkState, LinkStatus, TransportError } from "../bridge/types";

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

/** A probe could not be delivered (the IPC itself rejected, not the brain). */
export function linkProbeEnded(link: LinkView): LinkView {
  return link.probing ? { ...link, probing: false } : link;
}

/** The brain streamed a turn event, which proves it is serving without a probe. */
export function linkServing(link: LinkView): LinkView {
  return link.state === "ready" ? link : { ...link, state: "ready", detail: "" };
}

/**
 * A turn failed at the transport, which proves the same things a probe failure does and is
 * classified the same way (`body_core::link`): unreachable is `down`, a call that ran out of
 * time is `down` too (nothing answered), and an answered-but-wrong call (a non-OK status, an
 */
export function linkFailed(link: LinkView, error: TransportError): LinkView {
  const answered = error.kind !== "connection" && error.kind !== "timeout";
  return {
    ...link,
    state: answered ? "degraded" : "down",
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
