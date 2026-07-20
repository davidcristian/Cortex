import type { MarkStyle } from "../mark/marks";
import { CONSOLE_TABS, type ConsoleTab } from "../overlay/overlayState";
import { AppearanceTab } from "./AppearanceTab";
import { PanelView } from "./PanelView";
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
    <PanelView title="Console" onClose={onClose}>
      <div className="tabs" role="tablist" aria-label="Console">
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
      {/* Named by `aria-label` rather than pointing at the tab's id: both the tab being left and
          the one arriving are mounted together for the length of the morph, so any id in here
          would be in the document twice while the panel crosses over. */}
      <div className="tabpanel" role="tabpanel" aria-label={TAB_LABELS[tab]}>
        {tab === "appearance" ? (
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
    </PanelView>
  );
}
