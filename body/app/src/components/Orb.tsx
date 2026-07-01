/** The minimized "thinking" orb: colorful, breathing, drifting (all CSS). Click reopens the turn. */
export function Orb({ onClick }: { readonly onClick: () => void }) {
  return (
    <button className="orb" onClick={onClick} aria-label="Reopen (still working)" type="button">
      <span className="halo" aria-hidden="true" />
    </button>
  );
}
