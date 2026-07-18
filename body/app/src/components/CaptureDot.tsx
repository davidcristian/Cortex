interface CaptureDotProps {
  readonly capturing: boolean;
}

/**
 * The header's screen-capture indicator (ADR-0029): lit from the moment the assistant looks at
 * the user's screen until the turn ends.
 *
 * A **consent surface**, not decoration. The capture tool ships without an approval card (a
 * screen read is neither outbound nor irreversible, and the card could not say what will be
 * captured, since the call takes no arguments), so what the user is owed instead is a plain
 * statement that it happened. It stays lit for the whole turn rather than blinking past with
 * the tool chip, because "the assistant looked at my screen just now" is the fact, not "a tool
 * ran for a moment". The body fires its own OS notification independently; this is the half the
 * user is already looking at.
 *
 * Renders nothing when no capture has happened, on the same rule the connection dot follows:
 * chrome earns its place by meaning something.
 */
export function CaptureDot({ capturing }: CaptureDotProps) {
  if (!capturing) {
    return null;
  }
  const label = "The assistant looked at your screen during this reply";
  return <span className="capturedot" role="status" aria-label={label} title={label} />;
}
