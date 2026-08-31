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

/** How far apart two tabs may stand, in px, and still be shown at one shared height. Both tabs
 *  are mounted in one grid cell, so the taller one decides the panel's height and switching tabs
 *  resizes nothing. Past this many pixels the tab on screen gets its own height instead. */
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

/** The console: everything about the overlay that is not the conversation, behind one back
 *  chevron. */
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
  const stack = useRef<HTMLDivElement>(null!);
  // The pane ids below are the only names the overlay puts in the document's global namespace, so
  // they come from `useId` rather than from a literal that could collide.
  const ids = useId();
  const paneId = (name: ConsoleTab) => `${ids}${name}`;
  // The selected tab's button. React reattaches this ref to the newly selected button before the
  // effect below runs, because a child's refs are attached before an ancestor's layout effects.
  const selected = useRef<HTMLButtonElement>(null!);

  // Focus follows the selection on the way in and at every switch after it. The switch that needs
  // it is `?`, a global key that can change the tab while the keyboard is down in the pane being
  // left. Without `preventScroll` the engine scrolls the clipped panel to reach the new button.
  useLayoutEffect(() => {
    selected.current.focus({ preventScroll: true });
  }, [tab]);

  const onStripKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const to = nextTab(event.key, CONSOLE_TABS, tab);
    if (to === null) {
      return;
    }
    // Selection follows focus: both panes are already mounted, so showing one costs nothing.
    event.preventDefault();
    onSelectTab(to);
  };

  // Which shape the stack is in, decided by measuring the tabs. A layout effect and a direct
  // write, because `usePanelMotion`'s layout effect runs after this one, so the height the panel
  // eases to is the one decided here.
  useLayoutEffect(() => {
    const element = stack.current;
    // A pane stretched to the grid cell reports the cell's height, so both panes would report the
    // taller one's and the difference would always be zero. This attribute unstretches them for
    // one synchronous read, which paints nothing.
    element.setAttribute(MEASURING_ATTRIBUTE, "");
    const heights = [...element.children].map((pane) => (pane as HTMLElement).offsetHeight);
    element.removeAttribute(MEASURING_ATTRIBUTE);
    const tallest = Math.max(...heights);
    element.classList.toggle(APART_CLASS, tallest - Math.min(...heights) > TAB_SPREAD_PX);
    // How far the stack falls short of its tallest tab, so the panel places the console by the
    // height it can grow to. Read after the class above, because the class changes the stack's
    // height: sharing a height it is zero, which is correct.
    element.setAttribute(TAB_SLACK_ATTRIBUTE, String(tallest - element.offsetHeight));
  });

  return (
    <section className="pane" aria-label="Settings">
      {/* One line of chrome: the back button and the strip naming which tab is showing. A title
          above a strip that already names both tabs would state the same fact twice. */}
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
            aria-controls={paneId(name)}
            // A roving `tabindex`: the whole strip is one stop in the tab order.
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
      {/* Both tabs are mounted and stacked in one grid cell, and `TAB_SPREAD_PX` above decides
          whether they share a height. The stylesheet's `visibility: hidden` arrives only after the
          200ms fade, so `withdrawn` takes the hidden pane out of the tab order right away. */}
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
