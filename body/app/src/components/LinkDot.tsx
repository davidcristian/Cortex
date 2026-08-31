import { type LinkView, describeLink } from "../overlay/linkState";

interface LinkDotProps {
  readonly link: LinkView;
}

/**
 * The header's connection indicator (design/overlay-ux.md §3): green ready, amber reachable but
 * not serving, red unreachable, neutral before anything is known, pulsing while a probe is out.
 *
 * The first version of this dot was always green and was removed on 2026-07-03 because it reported
 * nothing. This one shows only what the last probe established, and states it in a label a pointer
 * or a screen reader can read, since a colour alone explains nothing.
 */
export function LinkDot({ link }: LinkDotProps) {
  const { tone, busy, label } = describeLink(link);
  return (
    <span
      className={`linkdot ${tone}${busy ? " busy" : ""}`}
      role="status"
      aria-label={label}
      title={label}
    />
  );
}
