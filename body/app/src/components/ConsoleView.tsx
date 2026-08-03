import { type KeyboardEvent, useId, useLayoutEffect, useRef } from "react";

import type { EdgeStyle } from "../edge/edges";
import type { MarkStyle } from "../mark/marks";
import { TAB_SLACK_ATTRIBUTE } from "../overlay/morph";
import { CONSOLE_TABS, type ConsoleTab } from "../overlay/overlayState";
import { nextTab } from "../overlay/tabStrip";
import { withdrawn } from "../overlay/withdrawn";
import { AppearanceTab } from "./AppearanceTab";
import { BackIcon } from "./icons";
import { ShortcutsTab } from "./ShortcutsTab";

/** How far apart two tabs may stand, in px, and still be held at one shared height. */
export const TAB_SPREAD_PX = 15;

/** Set on the stack for the length of one synchronous measurement, never across a paint. */
const MEASURING_ATTRIBUTE = "data-measuring";

/** Set on the stack while the tab on screen owns the height, rather than the taller of the two. */
const APART_CLASS = "apart";

/** How each tab is named on the strip. */
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

/**
 * The console: everything about the overlay that is not the conversation, behind one back
 * chevron. Appearance (ADR-0032) and the shortcut list used to be two views of the panel, which
 * made Esc a two-step exit and gave the user two ways in to one small pile of settings.
 */
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
  // One prefix per mounted console, rather than a name this file invents. The ids below are the
  // only thing the overlay puts in the document's global namespace, and a hand-written one is a
  // collision waiting for the second thing that wants it; `useId` is React's answer to exactly that.
  const ids = useId();
  const paneId = (name: ConsoleTab) => `${ids}${name}`;
  // The tab that is up, whichever one that is: the ref rides the selection from button to button,
  // and React has attached it to the new one before the effect below runs (a child's refs are
  // attached before an ancestor's layout effects).
  const selected = useRef<HTMLButtonElement>(null!);

  useLayoutEffect(() => {
    // Without scrolling anything, for the reason the composer's focus gives at length: the panel
    // clips its overflow, which makes it a scroll container the user cannot scroll and the engine
    // can, and bringing a newly focused element into view is exactly when it does.
    selected.current.focus({ preventScroll: true });
  }, [tab]);

  // The strip's keys, one handler on the strip rather than one per tab: which tab has focus is the
  // tab that is selected (that is what the roving `tabindex` below guarantees), so the key does not
  // need to ask the event which button it came from.
  const onStripKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const to = nextTab(event.key, CONSOLE_TABS, tab);
    if (to === null) {
      return;
    }
    event.preventDefault();
    onSelectTab(to);
  };

  useLayoutEffect(() => {
    const element = stack.current;
    element.setAttribute(MEASURING_ATTRIBUTE, "");
    const heights = [...element.children].map((pane) => (pane as HTMLElement).offsetHeight);
    element.removeAttribute(MEASURING_ATTRIBUTE);
    const tallest = Math.max(...heights);
    element.classList.toggle(APART_CLASS, tallest - Math.min(...heights) > TAB_SPREAD_PX);
    element.setAttribute(TAB_SLACK_ATTRIBUTE, String(tallest - element.offsetHeight));
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
        <div className="tabs" role="tablist" aria-label="Settings" onKeyDown={onStripKey}>
        {CONSOLE_TABS.map((name) => (
          <button
            key={name}
            className={`tab${name === tab ? " on" : ""}`}
            type="button"
            role="tab"
            aria-selected={name === tab}
            // Which pane this face is the handle for. The two already read alike, the pane taking
            // its name from the same label as the tab, but a reader offering "move to the panel"
            // needs the pointer rather than the coincidence.
            aria-controls={paneId(name)}
            tabIndex={name === tab ? 0 : -1}
            ref={name === tab ? selected : null}
            onClick={() => onSelectTab(name)}
          >
            {TAB_LABELS[name]}
          </button>
        ))}
        </div>
        <span className="hspacer" aria-hidden="true" />
      </header>
      <div className="tabstack" ref={stack}>
        {CONSOLE_TABS.map((name) => (
          <div
            key={name}
            id={paneId(name)}
            className={`tabpane${name === tab ? " on" : ""}`}
            role="tabpanel"
            aria-label={TAB_LABELS[name]}
            {...withdrawn(name !== tab)}
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
