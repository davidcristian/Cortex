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

/** One choice, shown rather than named: its art above, its name under it. */
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

/** The console's appearance tab: the choices that decide how the overlay looks, each made by
 *  looking at the thing rather than reading its name. Every row maps over its registry (`THEMES`,
 *  `MARKS`, `EDGES`), so a new theme, mark or edge needs no change here. */
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
      {/* The three legends are the console's own names for what each row changes. */}
      <section className="swatch">
        <h3 className="sect">Light</h3>
        <div className="tiles" role="radiogroup" aria-label="Light">
          {/* Auto comes first because it is the only choice the header's toggle cannot set: that
              toggle names the opposite theme and can only reach one of the two. */}
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
        {/* The chosen style's own note. What differs between the four styles is how they move,
            which a label cannot show. */}
        <p className="note">{mark.note}</p>
      </section>
      <section className="swatch">
        <h3 className="sect">Dream</h3>
        <div className="tiles" role="radiogroup" aria-label="Dream">
          {/* The registry's order, Still to Trance, is increasing intensity, so the row needs no
              caption. */}
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
