import { causticPath, envelopeAt, highlightsOf, lobeAt, lobePath } from "../mark/bubble";
import type { Lobe, PlacedLobe } from "../mark/bubble";
import type { MarkStyle } from "../mark/marks";
import { useMarkClock } from "../mark/useMarkClock";

// The Cortex mark: a soap bubble (design/overlay-ux.md §4). Layers, back to front: an outer bloom,
// the glass body, the film (a thick blurred stroke clipped to the outline, so the color hugs the
// inside of the rim the way a thinning film does), the crisp rim, the caustic on the far side, and
// the two reflections of a light source that never moves while the film rotates under it. Which
// bubble is drawn is data (mark/marks.ts); this renders any of them. `idPrefix` keeps the SVG
// gradient and clip ids unique per mount: ids are document-global and marks can co-exist.
//
// The eight-hue palette, carried over from the rings it replaced: one gradient, not two
// arcs, so the identity survived the shape change.
const PALETTE = [
  "#43d675",
  "#ffb347",
  "#ff5f6d",
  "#e055d8",
  "#3fa2ff",
  "#6a5cff",
  "#c44fd8",
  "#ffd23f",
] as const;

/** The mark's own coordinate box; every lobe in marks.ts is expressed in it. */
const VIEW = 100;
const FILM_OPACITY = 0.85;

interface BubbleMarkProps {
  readonly style: MarkStyle;
  readonly size: number;
  readonly idPrefix: string;
  readonly animated: boolean;
}

/** One rotating pass of the palette across the mark. */
function FilmGradient({ id, degrees }: { readonly id: string; readonly degrees: number }) {
  return (
    <linearGradient
      id={id}
      gradientUnits="userSpaceOnUse"
      x1="8"
      y1="8"
      x2="92"
      y2="92"
      gradientTransform={`rotate(${degrees.toFixed(2)} 50 50)`}
    >
      {PALETTE.map((color, index) => (
        <stop key={color} offset={`${(index / (PALETTE.length - 1)) * 100}%`} stopColor={color} />
      ))}
    </linearGradient>
  );
}

/** The parts of <defs> that never change: the glass body, the reflection falloff, the blurs. */
function StillDefs({ idPrefix }: { readonly idPrefix: string }) {
  return (
    <>
      <radialGradient id={`${idPrefix}-body`} cx="36%" cy="30%" r="76%">
        <stop offset="0%" stopColor="rgba(255,255,255,0.22)" />
        <stop offset="58%" stopColor="rgba(140,120,230,0.06)" />
        <stop offset="100%" stopColor="rgba(255,255,255,0.03)" />
      </radialGradient>
      <radialGradient id={`${idPrefix}-spec`}>
        <stop offset="0%" stopColor="#fff" stopOpacity="0.85" />
        <stop offset="62%" stopColor="#fff" stopOpacity="0.18" />
        <stop offset="100%" stopColor="#fff" stopOpacity="0" />
      </radialGradient>
      <filter id={`${idPrefix}-soft`} x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="4.2" />
      </filter>
      <filter id={`${idPrefix}-bloom`} x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="6" />
      </filter>
      <filter id={`${idPrefix}-edge`} x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="1.1" />
      </filter>
    </>
  );
}

interface LobeArtProps {
  readonly idPrefix: string;
  readonly index: number;
  readonly d: string;
  readonly placed: PlacedLobe;
  readonly filmOpacity: number;
  readonly innerFilmOpacity: number;
}

/** One bubble of the mark. */
function LobeArt({ idPrefix, index, d, placed, filmOpacity, innerFilmOpacity }: LobeArtProps) {
  const [wash, dot] = highlightsOf(placed);
  return (
    <g>
      <path className="mark-bloom" d={d} fill={`url(#${idPrefix}-film)`} opacity="0.3" filter={`url(#${idPrefix}-bloom)`} />
      <path className="mark-body" d={d} fill={`url(#${idPrefix}-body)`} />
      <g clipPath={`url(#${idPrefix}-clip${index})`}>
        <path
          className="mark-film"
          d={d}
          fill="none"
          stroke={`url(#${idPrefix}-film)`}
          strokeWidth={(placed.r * 0.72).toFixed(1)}
          filter={`url(#${idPrefix}-soft)`}
          opacity={filmOpacity.toFixed(2)}
        />
        <path
          className="mark-film-inner"
          d={d}
          fill="none"
          stroke={`url(#${idPrefix}-inner)`}
          strokeWidth={(placed.r * 0.4).toFixed(1)}
          filter={`url(#${idPrefix}-soft)`}
          opacity={innerFilmOpacity.toFixed(2)}
        />
      </g>
      <path
        className="mark-rim"
        d={d}
        fill="none"
        stroke={`url(#${idPrefix}-film)`}
        strokeWidth={(placed.r * 0.045 + 0.55).toFixed(2)}
        opacity="0.95"
      />
      <path
        className="mark-caustic"
        d={causticPath(placed)}
        fill="none"
        stroke="#fff"
        strokeWidth={(placed.r * 0.07).toFixed(2)}
        strokeLinecap="round"
        opacity="0.4"
        filter={`url(#${idPrefix}-edge)`}
      />
      <ellipse
        className="mark-wash"
        fill={`url(#${idPrefix}-spec)`}
        cx={wash.cx.toFixed(2)}
        cy={wash.cy.toFixed(2)}
        rx={wash.rx.toFixed(2)}
        ry={wash.ry.toFixed(2)}
        transform={`rotate(${wash.degrees} ${wash.cx.toFixed(2)} ${wash.cy.toFixed(2)})`}
      />
      <ellipse
        className="mark-spec"
        fill="#fff"
        opacity="0.8"
        cx={dot.cx.toFixed(2)}
        cy={dot.cy.toFixed(2)}
        rx={dot.rx.toFixed(2)}
        ry={dot.ry.toFixed(2)}
        transform={`rotate(${dot.degrees} ${dot.cx.toFixed(2)} ${dot.cy.toFixed(2)})`}
      />
    </g>
  );
}

/** A frame of one lobe: its outline and where it sits. */
function frameOf(lobe: Lobe, seconds: number): { readonly d: string; readonly placed: PlacedLobe } {
  return { d: lobePath(lobe, seconds), placed: lobeAt(lobe, seconds) };
}

export function BubbleMark({ style, size, idPrefix, animated }: BubbleMarkProps) {
  const seconds = useMarkClock(animated);
  const frames = style.lobes.map((lobe) => frameOf(lobe, seconds));
  const filmOpacity = FILM_OPACITY * (0.55 + 0.45 * envelopeAt(style.filmEnvelope, seconds));
  return (
    <svg
      className="mark"
      viewBox={`0 0 ${VIEW} ${VIEW}`}
      width={size}
      height={size}
      aria-hidden="true"
    >
      <defs>
        <FilmGradient id={`${idPrefix}-film`} degrees={(seconds / style.filmPeriodSeconds) * 360} />
        <FilmGradient
          id={`${idPrefix}-inner`}
          degrees={-(seconds / style.innerFilmPeriodSeconds) * 360}
        />
        <StillDefs idPrefix={idPrefix} />
        {frames.map((frame, index) => (
          <clipPath key={`${idPrefix}-clip${index}`} id={`${idPrefix}-clip${index}`}>
            <path d={frame.d} />
          </clipPath>
        ))}
      </defs>
      {frames.map((frame, index) => (
        <LobeArt
          key={`${idPrefix}-lobe${index}`}
          idPrefix={idPrefix}
          index={index}
          d={frame.d}
          placed={frame.placed}
          filmOpacity={filmOpacity}
          innerFilmOpacity={style.innerFilmOpacity}
        />
      ))}
    </svg>
  );
}
