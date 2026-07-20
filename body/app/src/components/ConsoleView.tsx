import type { MarkStyle } from "../mark/marks";
import { CONSOLE_TABS, type ConsoleTab } from "../overlay/overlayState";
import { AppearanceTab } from "./AppearanceTab";
import { BackIcon } from "./icons";
import { ShortcutsTab } from "./ShortcutsTab";

/** How each tab is named on the strip. Beside `CONSOLE_TABS` rather than inside it: the reducer's
 *  list is the state machine's, and how a tab is worded is this view's business. */
const TAB_LABELS: Record<ConsoleTab, string> = {
  appearance: "Appearance",
  shortcuts: "Shortcuts",
};

interface ConsoleViewProps {
  readonly tab: ConsoleTab;
  /** The chosen theme name, or `null` while the overlay follows the system scheme. */
  readonly themeName: string | null;
  readonly mark: MarkStyle;
  readonly animated: boolean;
  readonly onPickTheme: (name: string | null) => void;
  readonly onPickMark: (name: string) => void;
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
  animated,
  onPickTheme,
  onPickMark,
  onSelectTab,
  onClose,
}: ConsoleViewProps) {
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
      {/* Both tabs are mounted, stacked in one grid cell, and the taller one decides the height.
          Switching tabs therefore does not resize the panel at all: measured, the two are 335px and
          347px apart, and a window that jumps 12px and back reads as a flinch rather than as a
          change of view. A threshold could let a genuinely taller tab shrink the panel back, but
          there is no such tab to design against yet, and this is the shape that needs no number.

          The inactive tab keeps its box (that is the point) and gives up everything else: it is
          hidden from assistive tech and from the pointer, and `visibility` is what takes it out of
          the tab order too, which `opacity` alone would not. */}
      <div className="tabstack">
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
                animated={animated}
                onPickTheme={onPickTheme}
                onPickMark={onPickMark}
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
