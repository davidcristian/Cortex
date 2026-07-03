import { wavyRingPath } from "./ring";

// The Cortex mark: two counter-woven wavy bands, each stroked with a run of the accent hues.
// Rendered geometry is static. Motion (counter-spin, breathing, hue drift) lives in CSS and
// only under `.orb`, so small resting uses (the preview title) stay still. `idPrefix` keeps the
// SVG gradient ids unique per mount: ids are document-global and the marks can co-exist.
interface RingMarkProps {
  readonly size: number;
  readonly idPrefix: string;
  readonly strokeWidth: number;
}

export function RingMark({ size, idPrefix, strokeWidth }: RingMarkProps) {
  return (
    <svg className="rings" viewBox="0 0 64 64" width={size} height={size} aria-hidden="true">
      <defs>
        <linearGradient id={`${idPrefix}-band-a`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#8B5CF6" />
          <stop offset="45%" stopColor="#E24BC4" />
          <stop offset="75%" stopColor="#FF7A6B" />
          <stop offset="100%" stopColor="#4FE3D0" />
        </linearGradient>
        <linearGradient id={`${idPrefix}-band-b`} x1="1" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#4FE3D0" />
          <stop offset="55%" stopColor="#8B5CF6" />
          <stop offset="100%" stopColor="#E24BC4" />
        </linearGradient>
      </defs>
      <path
        className="ring ring-a"
        d={wavyRingPath(32, 23, 2.4, 7, 0)}
        stroke={`url(#${idPrefix}-band-a)`}
        strokeWidth={strokeWidth}
        fill="none"
      />
      <path
        className="ring ring-b"
        d={wavyRingPath(32, 23, 2, 9, 1.1)}
        stroke={`url(#${idPrefix}-band-b)`}
        strokeWidth={strokeWidth}
        fill="none"
      />
    </svg>
  );
}
