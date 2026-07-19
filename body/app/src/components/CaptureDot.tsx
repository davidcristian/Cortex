interface CaptureDotProps {
  readonly capturing: boolean;
}

/**
 * The header's screen-capture indicator (ADR-0029): lit from the moment the assistant asks to
 * look at the user's screen until the turn ends.
 */
export function CaptureDot({ capturing }: CaptureDotProps) {
  if (!capturing) {
    return null;
  }
  const label = "The assistant asked to look at your screen during this reply";
  return <span className="capturedot" role="status" aria-label={label} title={label} />;
}
