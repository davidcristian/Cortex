import { RingMark } from "./RingMark";

/** The minimized "thinking" mark: the living rings with one slow spin (mark + gradient together,
 *  CSS) with independent wave-depth pulses (SMIL, skipped under reduced motion). Click reopens
 *  the in-progress turn. */
export function Orb({ onClick }: { readonly onClick: () => void }) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return (
    <button className="orb" onClick={onClick} aria-label="Reopen (still working)" type="button">
      <RingMark size={64} idPrefix="orb" strokeWidth={2} animated={!reduced} />
    </button>
  );
}
