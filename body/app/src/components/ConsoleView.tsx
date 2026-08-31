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

/**
 * How far apart two tabs may stand, in px, and still be held at one shared height.
 *
 * Both tabs are mounted and stacked in one grid cell, so the taller of them decides the panel's
 * height and switching tabs resizes nothing. That suits two tabs of similar height: measured in
 * Chromium at a 640x720 window the appearance tab measures 278px and the shortcut list 290px, and a
 * window that jumps 12px and back reads as a twitch rather than as a change of view. It stops
 * suiting them once one tab is much shorter than the other, where holding the taller one's height
 * leaves a band of empty panel under the content and the window looks fuller than it is. Past this
 * many pixels the tab on screen is given its own height and the panel morphs to fit it.
 *
 * Raising this number holds more pairs at one height; lowering it lets more of them resize. No
 * other code changes either way.
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
 *  made Esc a two-step exit and gave the user two ways in to one small set of settings.
 *
 *  Each tab is its own view of the panel (`Panel` routes on `console:<tab>`), so switching tabs is
 *  the same resize-and-recentre morph as opening the console and reuses the cross-fade a view
 *  change already carries. No animation is defined here.
 *
 *  The tab strip is neutral fill with no accent, as the header buttons and the shortcut caps are.
 *  The only colour on this surface belongs to the marks, which are what is being chosen. */
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
  // only thing the overlay puts in the document's global namespace, so a hand-written one could
  // collide with the next thing that wants that name; `useId` avoids that.
  const ids = useId();
  const paneId = (name: ConsoleTab) => `${ids}${name}`;
  // The selected tab's button. React reattaches this ref to the newly selected button before the
  // effect below runs, because a child's refs are attached before an ancestor's layout effects.
  const selected = useRef<HTMLButtonElement>(null!);

  // Focus follows the selection, on the way in and at every switch after it.
  //
  // On the way in this does what `autoFocus` did: the console arrives, its selected tab takes the
  // keyboard, and the chat pane it came from is one morph from being removed from under whatever
  // had focus there.
  //
  // Written as an effect it also covers the three switches, which `autoFocus` never did. The
  // strip's own arrows land here already, so this is a no-op for them. A click arrives here with
  // focus on the button the pointer pressed, so it is a no-op for that too. The third is the one
  // this repairs: `?` is a global key and toggles the shortcut tab from anywhere, so it can change
  // the tab while the keyboard is down in the pane being left, and that pane is about to go inert.
  useLayoutEffect(() => {
    // Without scrolling anything, for the reason the composer's focus gives at length: the panel
    // clips its overflow, which makes it a scroll container the user cannot scroll and the engine
    // can, and bringing a newly focused element into view is when it does.
    selected.current.focus({ preventScroll: true });
  }, [tab]);

  // The strip's keys, one handler on the strip rather than one per tab: the tab with focus is
  // always the selected tab (the roving `tabindex` below guarantees that), so the handler does not
  // need to read which button the event came from.
  const onStripKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const to = nextTab(event.key, CONSOLE_TABS, tab);
    if (to === null) {
      return;
    }
    // Selection follows focus, which the recommended tabs pattern does wherever showing a panel
    // costs nothing. Here it costs nothing twice over: both panes are already mounted and
    // stacked, so there is no load and no latency, and at the shipping spread they share a height,
    // so the panel does not resize. Manual activation would also make the keyboard spend two
    // keystrokes on what one click does, on a surface whose whole content is reversible
    // preferences.
    event.preventDefault();
    onSelectTab(to);
  };

  // Which of the two shapes the stack is in, decided by measuring the tabs rather than from a list
  // of which pairs happen to be close in height. A layout effect and a direct write, because the
  // panel measures the result: `usePanelMotion`'s own layout effect runs after this one (React
  // flushes a child's before its parent's), so the height the panel eases to is the one decided
  // here and no render of the panel sees the other one.
  useLayoutEffect(() => {
    const element = stack.current;
    // Measured in a state the stack does not otherwise hold. A pane stretched to the cell reports
    // the cell's height, which is the taller tab's, so both panes would report the same number and
    // the difference being measured would always be zero. Unstretched, each reports its own
    // height. One synchronous read, so nothing paints in this state, and the grid's row is sized to
    // the taller pane either way, so the row does not move.
    element.setAttribute(MEASURING_ATTRIBUTE, "");
    const heights = [...element.children].map((pane) => (pane as HTMLElement).offsetHeight);
    element.removeAttribute(MEASURING_ATTRIBUTE);
    const tallest = Math.max(...heights);
    element.classList.toggle(APART_CLASS, tallest - Math.min(...heights) > TAB_SPREAD_PX);
    // How far the stack falls short of its tallest tab, which the panel uses to place the console
    // by the height it can grow to rather than by the height it was entered on. Read after the
    // class above, and off the stack rather than off a pane picked out of the list, so one
    // subtraction covers both shapes with no lookup that could miss: apart, the pane that is not
    // showing leaves the flow and the stack stands at the showing pane's height; sharing, the cell
    // is the taller pane's and the subtraction is zero, which is correct in that mode.
    element.setAttribute(TAB_SLACK_ATTRIBUTE, String(tallest - element.offsetHeight));
  });

  return (
    <section className="pane" aria-label="Settings">
      {/* One line of chrome: the back button and the strip naming which tab is showing. A title
          over a strip that already names both tabs stated the same fact twice, and the panel is
          short enough that an extra row is visible. */}
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
            // Which pane this tab controls. The tab and its pane already carry the same label, but
            // a screen reader offering "move to the panel" needs the id rather than the matching
            // text.
            aria-controls={paneId(name)}
            // A roving `tabindex`: the whole strip is one stop in the page's tab order, and Tab
            // arrives on the selected tab rather than walking the buttons one by one. With
            // selection following focus this needs no state of its own, because the tab with focus
            // and the selected tab are the same tab, so this and `aria-selected` are two readings
            // of one fact rather than two values that could disagree.
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
      {/* Both tabs are mounted and stacked in one grid cell. `TAB_SPREAD_PX` above decides whether
          the taller one sets the height for both or the tab on screen sets its own and the panel
          morphs: close together they share a height, far apart they do not. The two that ship today
          are 12px apart, so they share and switching tabs moves nothing.

          While they share, the inactive tab keeps its box and loses everything else.
          `visibility: hidden` in the stylesheet does most of that, but it arrives on a delay,
          because the fade has to finish before the pane is removed; for those 200ms the pane was
          announced as hidden and still tabbable, and Tab pressed inside that window walked into it
          (measured: six stops among the theme and mark tiles of the tab being left, and then the
          body, when `visibility` landed and dropped focus out of an element that had it).
          `withdrawn` closes that window by taking the pane out of the tab order in the same frame
          it stops being the selected tab. */}
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
