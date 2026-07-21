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

/** One choice, shown rather than named: its art above, its name under it. The chosen tile is
 *  lifted out of the row (a fill and a hairline); the rest rest. No accent anywhere, because a
 *  swatch is resting chrome even when the thing it draws is not (design/overlay-ux.md §1).
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

/** The console's appearance tab (ADR-0032): the two choices that decide how the overlay looks,
 *  each made by looking at the thing rather than reading its name. Themes are miniature panels
 *  wearing themselves; marks are the real `BubbleMark`, drawn live and large enough that four
 *  styles that differ by how they MOVE can be told apart by watching them.
 *
 *  Both rows are a map over their registry (`THEMES`, `MARKS`), so a fifth theme or a fifth mark
 *  style is a literal in that registry and no change here. That plug-and-play property is the
 *  stated invariant of both modules, and this view is built to keep it rather than to restate the
 *  four names it happens to ship with. */
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
      <section className="swatch">
        <h3 className="sect">Theme</h3>
        <div className="tiles" role="radiogroup" aria-label="Theme">
          {/* Auto leads, because it is the only choice the header's toggle cannot express: that
              toggle names the opposite theme outright and can only ever land on one of the two. The
              tile is not captioned "Auto follows your system": the word Auto on a tile split between
              the two themes beside it already says it, and a line of prose under three pictures is
              the picture explained to someone who has just looked at it. */}
          <Tile label="Auto" checked={themeName === null} onPick={() => onPickTheme(null)}>
            <AutoMini />
          </Tile>
          {THEMES.map((theme) => (
            <Tile
              key={theme.name}
              label={theme.name}
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
        {/* The chosen style's own note, under the row it belongs to: what moves is the thing being
            chosen, and one line of it beats four labels nobody can tell apart. */}
        <p className="note">{mark.note}</p>
      </section>
      <section className="swatch">
        <h3 className="sect">Window</h3>
        <div className="tiles" role="radiogroup" aria-label="Window">
          {/* The registry's own order is the ladder, Still to Trance, so the row explains
              intensity without a caption (ADR-0036). A map over the registry, like the rows
              above: a fifth edge appears here with no change to this view. */}
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
