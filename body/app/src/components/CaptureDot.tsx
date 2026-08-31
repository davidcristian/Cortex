import type { CaptureClaim } from "../overlay/overlayState";

interface CaptureDotProps {
  readonly claim: CaptureClaim | null;
}

/** What each level of the claim is allowed to state, and nothing more (ADR-0029). The label is the
 *  consent surface, because a colour explains nothing, so the accessible name and the tooltip carry
 *  the whole statement, as the connection dot's do. */
const LABELS: Record<CaptureClaim, string> = {
  asked: "The assistant asked to look at your screen during this reply",
  read: "The assistant looked at your screen during this reply",
};

/* Neither label distinguishes one window from the whole screen. `ToolOutcome` carries a tool name
 * and a boolean, so nothing here could tell them apart without a wider event, and a window is part
 * of the screen, so the coarser sentence is true of both. Where this surface has to be wrong, it
 * is wrong by claiming more than happened rather than less. */

/**
 * The header's screen-capture indicator (ADR-0029): lit from the moment the assistant asks to
 * look at the user's screen until the turn ends.
 *
 * This is a **consent surface**. The capture tool ships without an approval card (a screen read is
 * neither outbound nor irreversible, and a gated call on a tainted turn is denied before a card is
 * shown), so the user gets a plain statement that it happened instead. It stays lit for the whole
 * turn rather than appearing briefly with the tool chip, because what the user needs to know is
 * that the assistant read the screen during this reply. The body fires its own OS notification
 * independently; this is the half the user is already looking at.
 *
 * **Two levels, because the seam reports two things.** The `ToolActivity` chip is emitted just
 * before dispatch, so on its own it establishes only that the assistant asked; the `ToolOutcome`
 * that settles the dispatch is what raises the claim to "looked". The weaker level is reached
 * often: the host kill switch is off by default, the overlay's self-exclusion can fail closed, the
 * body can be unreachable or time out, and a user who gated the tool can decline the card, and all
 * four leave the claim at "asked".
 *
 * **A failed outcome does not lower the claim.** It leaves the ring where the ask put it rather
 * than dimming it, because from the brain's side a capture that failed after the screen was read
 * is indistinguishable from one that never happened, and claiming more than happened is the safe
 * direction for a privacy indicator.
 *
 * Renders nothing when no capture has been asked for, on the same rule the connection dot follows.
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
