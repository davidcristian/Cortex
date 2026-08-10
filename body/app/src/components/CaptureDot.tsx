import type { CaptureClaim } from "../overlay/overlayState";

interface CaptureDotProps {
  readonly claim: CaptureClaim | null;
}

/** What each rung of the claim is allowed to say, and nothing more (ADR-0029). The label IS the
 *  consent surface: a colour explains nothing, so the accessible name and the tooltip carry the
 *  whole statement, exactly as the connection dot's do. */
const LABELS: Record<CaptureClaim, string> = {
  asked: "The assistant asked to look at your screen during this reply",
  read: "The assistant looked at your screen during this reply",
};

/* Neither label distinguishes one window from the whole screen, and that is not an omission the
 * capture target reopened. `ToolOutcome` carries a name and a bit, so nothing here could tell
 * them apart without a wider event, and a window IS part of the screen, so the coarser sentence
 * is true of both. Over-reporting is the direction this surface is built to fail in. */

/**
 * The header's screen-capture indicator (ADR-0029): lit from the moment the assistant asks to
 * look at the user's screen until the turn ends.
 *
 * A **consent surface**, not decoration. The capture tool ships without an approval card (a
 * screen read is neither outbound nor irreversible, and a gated call on a tainted turn is denied
 * before the card is ever shown), so what the user is owed instead is a plain statement that it
 * happened. It stays lit for the whole turn rather than blinking past with
 * the tool chip, because "the assistant went for my screen during this reply" is the fact, not
 * "a tool ran for a moment". The body fires its own OS notification independently; this is the
 * half the user is already looking at.
 *
 * **Two rungs, because the seam now proves two things.** The `ToolActivity` chip is emitted just
 * *before* dispatch, so on its own it proves only that the assistant asked; the `ToolOutcome`
 * that settles the dispatch is what raises the claim to "looked". The weaker rung is not a
 * fallback nobody reaches: the host kill switch is off by default, the overlay's self-exclusion
 * can fail closed, the body can be unreachable or time out, and a user who gated the tool can
 * decline the card, and all four still say "asked".
 *
 * **The ring only ever deepens.** A failed outcome leaves the ring exactly where the ask put it
 * rather than dimming it, because from the brain's side a capture that failed *after* the
 * shutter fired is indistinguishable from one that never happened. Over-reporting a screen read
 * is the safe direction for a privacy indicator; under-reporting is the one that would matter.
 *
 * Renders nothing when no capture has been asked for, on the same rule the connection dot
 * follows: chrome earns its place by meaning something.
 */
export function CaptureDot({ claim }: CaptureDotProps) {
  if (claim === null) {
    return null;
  }
  const label = LABELS[claim];
  return (
    <span
      className={claim === "read" ? "capturedot read" : "capturedot"}
      role="status"
      aria-label={label}
      title={label}
    />
  );
}
