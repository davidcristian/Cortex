import { type LinkView, describeLink } from "../overlay/linkState";

interface LinkDotProps {
  readonly link: LinkView;
}

/** The header's connection indicator (design/overlay-ux.md §3): green ready, amber reachable but
 *  not serving, red unreachable, neutral before anything is known, pulsing while a probe is out. */
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
