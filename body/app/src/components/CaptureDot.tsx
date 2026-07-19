interface CaptureDotProps {
  readonly capturing: boolean;
}

/**
 * The header's screen-capture indicator (ADR-0029): lit from the moment the assistant asks to
 * look at the user's screen until the turn ends.
 *
 * A **consent surface**, not decoration. The capture tool ships without an approval card (a
 * screen read is neither outbound nor irreversible, and the card could not say what will be
 * captured, since the call takes no arguments), so what the user is owed instead is a plain
 * statement that it happened. It stays lit for the whole turn rather than blinking past with
 * the tool chip, because "the assistant went for my screen during this reply" is the fact, not
 * "a tool ran for a moment". The body fires its own OS notification independently; this is the
 * half the user is already looking at.
 *
 * **It says "asked to look", not "looked", because that is all the seam proves.** The signal
 * behind it is the `ToolActivity` chip, which the brain emits just *before* dispatch, and a
 * capture can still fail afterwards: the host kill switch is off by default, the overlay's
 * self-exclusion can fail closed, the body can be unreachable or time out, and a user who
 * gated the tool can decline the card. None of those outcomes reaches the overlay, so a label
 * claiming the screen was read would be wrong in every one of them. Uninformative but never
 * wrong is the rule this indicator shares with the connection dot; the stronger surface (a
 * post-dispatch outcome on the seam) is a recorded deferral, not a thing to imply here.
 *
 * Renders nothing when no capture has been asked for, on the same rule the connection dot
 * follows: chrome earns its place by meaning something.
 */
export function CaptureDot({ capturing }: CaptureDotProps) {
  if (!capturing) {
    return null;
  }
  const label = "The assistant asked to look at your screen during this reply";
  return <span className="capturedot" role="status" aria-label={label} title={label} />;
}
