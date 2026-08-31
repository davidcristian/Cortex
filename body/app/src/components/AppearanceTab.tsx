import type { ReactNode } from "react";

import { EDGES, type EdgeStyle } from "../edge/edges";
import { MARKS, type MarkStyle } from "../mark/marks";
import { THEMES } from "../theme/themes";
import { BubbleMark } from "./BubbleMark";
import { EdgeMini } from "./EdgeMini";
import { AutoMini, ThemeMini } from "./ThemeMini";

interface AppearanceTabProps {
  /** The chosen theme name, or `null` while the overlay follows the system scheme. */
  readonly themeName: string | null;
  readonly mark: MarkStyle;
  readonly edge: EdgeStyle;
  readonly animated: boolean;
  readonly onPickTheme: (name: string | null) => void;
  readonly onPickMark: (name: string) => void;
  readonly onPickEdge: (name: string) => void;
}

interface TileProps {
  readonly label: string;
  readonly checked: boolean;
  /** Tooltip for a choice whose art is the whole explanation (a mark's one-line note). */
  readonly hint?: string;
  readonly onPick: () => void;
  readonly children: ReactNode;
}

/** One choice, shown rather than named: its art above, its name under it. The chosen tile takes a
 *  fill and a hairline and the others take neither. No accent anywhere, because a swatch is
 *  resting chrome even when the thing it draws is not (design/overlay-ux.md §1).
 *
 *  The visible name is also the accessible one: the art carries no text, so nothing here has a
 *  label the user cannot see. */
function Tile({ label, checked, hint, onPick, children }: TileProps) {
  return (
    <button
      className={`tile${checked ? " on" : ""}`}
      type="button"
      role="radio"
      aria-checked={checked}
      title={hint}
      onClick={onPick}
    >
      <span className="tile-art">{children}</span>
      <span className="tile-name">{label}</span>
    </button>
  );
}

/** The console's appearance tab (ADR-0032): the choices that decide how the overlay looks, each
 *  made by looking at the thing rather than reading its name. A theme tile is a miniature panel
 *  drawn in that theme's own tokens; a mark tile is the real `BubbleMark`, drawn live and large
 *  enough that four styles differing only in how they move can be told apart by watching them.
 *
 *  Every row is a map over its registry (`THEMES`, `MARKS`, `EDGES`), so a fifth theme, mark or
 *  edge is a literal in that registry and needs no change here. That plug-and-play property is the
 *  stated invariant of those modules, and this view is written to keep it rather than to restate
 *  the names it happens to ship with. */
export function AppearanceTab({
  themeName,
  mark,
  edge,
  animated,
  onPickTheme,
  onPickMark,
  onPickEdge,
}: AppearanceTabProps) {
  return (
    <div className="rows">
      {/* The three legends name the dimension each row varies along, in the one anatomy: the
          face has a light, an iris, and a dream. */}
      <section className="swatch">
        <h3 className="sect">Light</h3>
        <div className="tiles" role="radiogroup" aria-label="Light">
          {/* Auto comes first, because it is the only choice the header's toggle cannot express:
              that toggle names the opposite theme outright and can only land on one of the two. The
              tile carries no caption, because the word Auto on a tile split between the two themes
              beside it already says what it does. */}
          <Tile label="Auto" checked={themeName === null} onPick={() => onPickTheme(null)}>
            <AutoMini />
          </Tile>
          {THEMES.map((theme) => (
            <Tile
              key={theme.name}
              label={theme.label}
              checked={themeName === theme.name}
              onPick={() => onPickTheme(theme.name)}
            >
              <ThemeMini theme={theme} />
            </Tile>
          ))}
        </div>
      </section>
      <section className="swatch">
        <h3 className="sect">Iris</h3>
        <div className="tiles" role="radiogroup" aria-label="Iris">
          {MARKS.map((choice) => (
            <Tile
              key={choice.name}
              label={choice.label}
              hint={choice.note}
              checked={choice.name === mark.name}
              onPick={() => onPickMark(choice.name)}
            >
              <BubbleMark
                style={choice}
                size={40}
                idPrefix={`tile-${choice.name}`}
                animated={animated}
              />
            </Tile>
          ))}
        </div>
        {/* The chosen style's own note, under the row it belongs to. What differs between the four
            styles is how they move, which a label cannot show and one line of prose can. */}
        <p className="note">{mark.note}</p>
      </section>
      <section className="swatch">
        <h3 className="sect">Dream</h3>
        <div className="tiles" role="radiogroup" aria-label="Dream">
          {/* The registry's own order is the ladder, Still to Trance, so the row shows increasing
              intensity without a caption (ADR-0036). A map over the registry, like the rows above,
              so a fifth edge appears here with no change to this view. */}
          {EDGES.map((choice) => (
            <Tile
              key={choice.name}
              label={choice.label}
              hint={choice.note}
              checked={choice.name === edge.name}
              onPick={() => onPickEdge(choice.name)}
            >
              <EdgeMini style={choice} idPrefix={`tile-edge-${choice.name}`} animated={animated} />
            </Tile>
          ))}
        </div>
        <p className="note">{edge.note}</p>
      </section>
    </div>
  );
}
