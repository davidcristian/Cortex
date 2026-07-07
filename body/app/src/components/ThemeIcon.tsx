const RAY_ANGLES = [0, 45, 90, 135, 180, 225, 270, 315];

// The theme toggle's face: a hollow sun that morphs into a hollow crescent. Both forms are drawn,
// and the CSS on `.sunmoon` cross-fades, spins and retracts them, so the switch is one movement
// rather than a swap of glyphs.
export function ThemeIcon({ dark }: { readonly dark: boolean }) {
  return (
    <svg
      className={`sunmoon${dark ? " dark" : ""}`}
      viewBox="0 0 24 24"
      width="16"
      height="16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <g className="sun">
        <circle cx="12" cy="12" r="4" />
        <g className="rays">
          {RAY_ANGLES.map((angle) => (
            <line key={angle} x1="12" y1="3.4" x2="12" y2="5.4" transform={`rotate(${angle} 12 12)`} />
          ))}
        </g>
      </g>
      <path className="moon" d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1 -9 -9z" />
    </svg>
  );
}
