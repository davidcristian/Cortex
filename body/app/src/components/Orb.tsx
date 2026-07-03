import { RingMark } from "./RingMark";

/** The minimized "thinking" mark: the living rings, counter-spinning, breathing, drifting
 *  (all CSS; see `.orb` in overlay.css). Click reopens the in-progress turn. */
export function Orb({ onClick }: { readonly onClick: () => void }) {
  return (
    <button className="orb" onClick={onClick} aria-label="Reopen (still working)" type="button">
      <RingMark size={64} idPrefix="orb" strokeWidth={2} />
    </button>
  );
}
