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

/**
 * The header's screen-capture indicator (ADR-0029): lit from the moment the assistant asks to
 * look at the user's screen until the turn ends.
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
