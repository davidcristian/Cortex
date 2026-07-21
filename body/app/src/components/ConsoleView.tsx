import { useLayoutEffect, useRef } from "react";

import type { EdgeStyle } from "../edge/edges";
import type { MarkStyle } from "../mark/marks";
import { CONSOLE_TABS, type ConsoleTab } from "../overlay/overlayState";
import { AppearanceTab } from "./AppearanceTab";
import { BackIcon } from "./icons";
import { ShortcutsTab } from "./ShortcutsTab";

/**
 * How far apart two tabs may stand, in px, and still be held at one shared height.
 *
 * Both tabs are mounted and stacked in one grid cell, so the taller of them decides the panel's
 * height and switching tabs resizes nothing. That is right while the two are close: measured in
 * Chromium at a 640x720 window the appearance tab wants 278px and the shortcut list 290px, and a
 * window that jumps 12px and back reads as a flinch rather than as a change of view. It stops being
 * right once a tab is genuinely shorter than its neighbour, where holding the taller one's height
 * leaves a band of empty panel under the content and the window is lying about how much is in it.
 * Past this many pixels the tab on screen is given its own height and the panel morphs to fit it.
 *
 * This is the only number in it, and it is the one to retune: raise it to hold more pairs still,
 * lower it to let more of them move. Nothing else has to change either way.
 */
export const TAB_SPREAD_PX = 15;

/** Set on the stack for the length of one synchronous measurement, never across a paint. */
const MEASURING_ATTRIBUTE = "data-measuring";

/** Set on the stack while the tab on screen owns the height, rather than the taller of the two. */
const APART_CLASS = "apart";

/** How each tab is named on the strip. Beside `CONSOLE_TABS` rather than inside it: the reducer's
 *  list is the state machine's, and how a tab is worded is this view's business. The pair speaks
 *  the overlay's own language (the AGENTS.md naming rule): Face is what it shows, the tab whose
 *  rows are its light, its iris, and its dream, the way a watch face names the appearance you put
 *  on the same watch; Chords is the term of art for the key combinations the other tab lists, the
 *  music you play on it. */
const TAB_LABELS: Record<ConsoleTab, string> = {
  appearance: "Face",
  shortcuts: "Chords",
};

interface ConsoleViewProps {
  readonly tab: ConsoleTab;
  /** The chosen theme name, or `null` while the overlay follows the system scheme. */
  readonly themeName: string | null;
  readonly mark: MarkStyle;
  readonly edge: EdgeStyle;
  readonly animated: boolean;
  readonly onPickTheme: (name: string | null) => void;
  readonly onPickMark: (name: string) => void;
  readonly onPickEdge: (name: string) => void;
  readonly onSelectTab: (tab: ConsoleTab) => void;
  readonly onClose: () => void;
}

/** The console: everything about the overlay that is not the conversation, behind one back
 *  chevron. Appearance (ADR-0032) and the shortcut list used to be two views of the panel, which
 *  made Esc a two-step exit and gave the user two ways in to one small pile of settings.
 *
 *  Each tab is its own view of the panel (`Panel` routes on `console:<tab>`), so switching tabs is
 *  the same resize-and-recentre morph as opening the console, and the cross-fade that already
 *  carries a view change carries this one for free. There is no second animation here.
 *
 *  The tab strip is resting chrome: neutral fill, no accent, the way the header buttons and the
 *  shortcut caps are. The only colour on this whole surface belongs to the marks, which are the
 *  thing being chosen. */
export function ConsoleView({
  tab,
  themeName,
  mark,
  edge,
  animated,
  onPickTheme,
  onPickMark,
  onPickEdge,
  onSelectTab,
  onClose,
}: ConsoleViewProps) {
  // The stack is mounted with the view, so the ref is set before any effect runs.
  const stack = useRef<HTMLDivElement>(null!);

  // Which of the two shapes the stack is in, decided from the tabs themselves rather than from a
  // list of which pairs happen to be close. A layout effect and a direct write, because the panel
  // measures the result: `usePanelMotion`'s own layout effect runs after this one (React flushes a
  // child's before its parent's), so the height the panel eases to is the one decided here, and no
  // render of the panel's ever sees the other one.
  useLayoutEffect(() => {
    const element = stack.current;
    // Measured in a pose the stack does not otherwise hold. A pane stretched to the cell reports
    // the CELL's height, which is the taller tab's, which is exactly the difference being looked
    // for: unstretched, each reports what it is worth. One synchronous read, so nothing paints in
    // this pose, and the grid's row is sized to the taller pane either way, so it does not move.
    element.setAttribute(MEASURING_ATTRIBUTE, "");
    const heights = [...element.children].map((pane) => (pane as HTMLElement).offsetHeight);
    element.removeAttribute(MEASURING_ATTRIBUTE);
    const spread = Math.max(...heights) - Math.min(...heights);
    element.classList.toggle(APART_CLASS, spread > TAB_SPREAD_PX);
  });

  return (
    <section className="pane" aria-label="Settings">
      {/* One line of chrome: the way back, and the strip saying which half you are looking at. A
          title over a strip that already names both tabs was the same fact told twice, and the
          panel is short enough that a row it does not need is a row you notice. */}
      <header className="head">
        <button className="hbtn" onClick={onClose} aria-label="Back to chat" type="button">
          <BackIcon />
        </button>
        <div className="tabs" role="tablist" aria-label="Settings">
        {CONSOLE_TABS.map((name) => (
          <button
            key={name}
            className={`tab${name === tab ? " on" : ""}`}
            type="button"
            role="tab"
            aria-selected={name === tab}
            // Focus follows the selection into the pane that arrives. The strip lives INSIDE the
            // pane and a tab change replaces the pane wholesale, so the button just clicked leaves
            // with it, and a moment later goes `display: none`, at which point the browser drops
            // focus to the body. Moving it here keeps the keyboard where the eye is, and it is also
            // what lets the leaving pane be hidden from assistive tech at all: Chromium refuses
            // aria-hidden over an ancestor of the focused element and says so in the console, so
            // without this the tab just left would stay in the tree as a second, equal console.
            autoFocus={name === tab}
            onClick={() => onSelectTab(name)}
          >
            {TAB_LABELS[name]}
          </button>
        ))}
        </div>
        <span className="hspacer" aria-hidden="true" />
      </header>
      {/* Both tabs are mounted and stacked in one grid cell. Whether the taller one decides the
          height for both, or the tab on screen decides its own and the panel morphs, is the one
          judgement above (`TAB_SPREAD_PX`): close together they share, far apart they do not. The
          two that ship today are 12px apart, so they share, and switching tabs moves nothing.

          The inactive tab keeps its box while they share (that is the point) and gives up
          everything else: it is hidden from assistive tech and from the pointer, and `visibility`
          is what takes it out of the tab order too, which `opacity` alone would not. */}
      <div className="tabstack" ref={stack}>
        {CONSOLE_TABS.map((name) => (
          <div
            key={name}
            className={`tabpane${name === tab ? " on" : ""}`}
            role="tabpanel"
            aria-label={TAB_LABELS[name]}
            aria-hidden={name !== tab}
          >
            {name === "appearance" ? (
              <AppearanceTab
                themeName={themeName}
                mark={mark}
                edge={edge}
                animated={animated}
                onPickTheme={onPickTheme}
                onPickMark={onPickMark}
                onPickEdge={onPickEdge}
              />
            ) : (
              <ShortcutsTab />
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
