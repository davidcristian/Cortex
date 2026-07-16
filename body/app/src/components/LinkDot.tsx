import { type LinkView, describeLink } from "../overlay/linkState";

interface LinkDotProps {
  readonly link: LinkView;
}

/**
 * The header's connection indicator (design/overlay-ux.md §3): green ready, amber reachable but
 * not serving, red unreachable, neutral before anything is known, pulsing while a probe is out.
 *
 * The v1 dot was always green and was removed for it (2026-07-03): chrome earns its place by
 * meaning something. This one only ever shows what the seam actually proved, and says so in a
 * label a pointer or a screen reader can read, since a colour alone is not an explanation.
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
