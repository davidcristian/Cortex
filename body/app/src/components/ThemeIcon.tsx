const RAY_ANGLES = [0, 45, 90, 135, 180, 225, 270, 315];

// The theme toggle's face: a single SVG sun that morphs into a crescent instead of swapping
// glyphs. The geometry that changes (core radius, the masking "bite" circle, ray retraction)
// is driven by CSS on `.sunmoon`/`.sunmoon.dark`, so the switch transitions smoothly.
export function ThemeIcon({ dark }: { readonly dark: boolean }) {
  return (
    <svg
      className={`sunmoon${dark ? " dark" : ""}`}
      viewBox="0 0 24 24"
      width="16"
      height="16"
      aria-hidden="true"
    >
      <mask id="theme-bite">
        <rect width="24" height="24" fill="#fff" />
        <circle className="bite" cx="30" cy="-6" r="7" fill="#000" />
      </mask>
      <circle className="core" cx="12" cy="12" r="5" mask="url(#theme-bite)" fill="currentColor" />
      <g className="rays" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
        {RAY_ANGLES.map((angle) => (
          <line key={angle} x1="12" y1="2.5" x2="12" y2="4.5" transform={`rotate(${angle} 12 12)`} />
        ))}
      </g>
    </svg>
  );
}
