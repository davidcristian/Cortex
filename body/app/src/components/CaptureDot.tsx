import type { CaptureClaim } from "../overlay/overlayState";

interface CaptureDotProps {
  readonly claim: CaptureClaim | null;
}

/** What each level of the claim is allowed to state, and nothing more. The label is what tells the
 *  user what happened, so it holds the whole statement; the colour alone explains nothing. */
const LABELS: Record<CaptureClaim, string> = {
  asked: "The assistant asked to look at your screen during this reply",
  read: "The assistant looked at your screen during this reply",
};

/** The header's screen-capture indicator: lit from the moment the assistant asks to look at the
 *  user's screen until the turn ends. A failed capture leaves the claim where the ask put it,
 *  because a capture that failed after the screen was read looks the same from here. */
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
