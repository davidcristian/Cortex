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

/**
 * The console: everything about the overlay that is not the conversation, behind one back
 * chevron. Appearance (ADR-0032) and the shortcut list used to be two views of the panel, which
 * made Esc a two-step exit and gave the user two ways in to one small pile of settings.
 */
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
