import { wavyRingPath } from "./ring";

// The Cortex mark: two wavy bands, each stroked with a run of the AI palette. The bands never
// rotate against each other. The whole mark spins as one (CSS, .orb only) while each band's
// *wave depth* pulses independently (the SMIL <animate> below, opt-in via `animated`), which is
// what keeps the weave lively without the tangled look. `idPrefix` keeps the SVG gradient ids
// unique per mount: ids are document-global and the marks can co-exist.
interface RingMarkProps {
  readonly size: number;
  readonly idPrefix: string;
  readonly strokeWidth: number;
  readonly animated: boolean;
}

const bandA = (depth: number): string => wavyRingPath(32, 23, depth, 7, 0);
const bandB = (depth: number): string => wavyRingPath(32, 23, depth, 9, 1.1);

/** A gentle there-and-back SMIL pulse over the given path snapshots. */
function DepthPulse({ dur, values }: { readonly dur: string; readonly values: readonly string[] }) {
  return (
    <animate
      attributeName="d"
      dur={dur}
      repeatCount="indefinite"
      calcMode="spline"
      keyTimes="0;0.5;1"
      keySplines="0.4 0 0.6 1;0.4 0 0.6 1"
      values={values.join(";")}
    />
  );
}

export function RingMark({ size, idPrefix, strokeWidth, animated }: RingMarkProps) {
  return (
    <svg className="rings" viewBox="0 0 64 64" width={size} height={size} aria-hidden="true">
      <defs>
        <linearGradient id={`${idPrefix}-band-a`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#38BDF8" />
          <stop offset="38%" stopColor="#8B5CF6" />
          <stop offset="70%" stopColor="#E24BC4" />
          <stop offset="100%" stopColor="#FF7A6B" />
        </linearGradient>
        <linearGradient id={`${idPrefix}-band-b`} x1="1" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#22D3EE" />
          <stop offset="35%" stopColor="#4FE3D0" />
          <stop offset="68%" stopColor="#6366F1" />
          <stop offset="100%" stopColor="#C084FC" />
        </linearGradient>
      </defs>
      <path
        className="ring ring-a"
        d={bandA(2.4)}
        stroke={`url(#${idPrefix}-band-a)`}
        strokeWidth={strokeWidth}
        fill="none"
      >
        {animated ? <DepthPulse dur="5s" values={[bandA(1.4), bandA(3.3), bandA(1.4)]} /> : null}
      </path>
      <path
        className="ring ring-b"
        d={bandB(2)}
        stroke={`url(#${idPrefix}-band-b)`}
        strokeWidth={strokeWidth}
        fill="none"
      >
        {animated ? <DepthPulse dur="3.6s" values={[bandB(2.9), bandB(1.2), bandB(2.9)]} /> : null}
      </path>
    </svg>
  );
}
