import { useRef } from "react";

import type { MarkStyle } from "../mark/marks";
import { CONSOLE_TABS, type ConsoleTab, type OverlayState } from "../overlay/overlayState";
import { MAX_DURATION_MS } from "../overlay/panelGeometry";
import { usePanelMotion } from "../overlay/usePanelMotion";
import { useViewTransition } from "../overlay/useViewTransition";
import { ChatView } from "./ChatView";
import { ConsoleView } from "./ConsoleView";

interface PanelProps {
  readonly state: OverlayState;
  readonly open: boolean;
  readonly dark: boolean;
  readonly mark: MarkStyle;
  /** The chosen theme name, or `null` while following the system scheme (the view shows it). */
  readonly themeName: string | null;
  readonly onPickTheme: (name: string | null) => void;
  readonly onPickMark: (name: string) => void;
  /** Open or close one console tab from its opener in the hint strip (the sliders, the ?). */
  readonly onToggleConsole: (tab: ConsoleTab) => void;
  /** Switch tabs from the strip inside the console; showing the tab already up is a no-op. */
  readonly onOpenConsole: (tab: ConsoleTab) => void;
  readonly onCloseConsole: () => void;
  readonly onToggleTheme: () => void;
  readonly onSubmit: (text: string) => void;
  readonly onStop: () => void;
  readonly onDismiss: () => void;
  readonly onNewChat: () => void;
  readonly onToggleSwitcher: () => void;
  readonly onSelectSession: (sessionId: string) => void;
  readonly onRenameSession: (sessionId: string, title: string) => void;
  readonly onDeleteSession: (sessionId: string) => void;
  readonly onPinSession: (sessionId: string, pinned: boolean) => void;
  readonly onRespondConfirm: (confirmId: string, approved: boolean) => void;
  readonly onDismissReminder: (reminderId: string) => void;
}

/** How long the outgoing view stays on screen. The panel's own morph in `usePanelMotion` scales
 *  with the distance it travels, so the fade is timed to that scale's own ceiling and imported from
 *  it rather than restated here: it outlasts every resize rather than ending inside one, and the
 *  view being left is never cut away mid-movement. */
const MORPH_MS = MAX_DURATION_MS;

/** A view of the panel. The console's TAB is part of the name on purpose: switching tabs is then a
 *  view change like any other, so it resizes and re-centres through the one motion the panel
 *  already has, and the cross-fade between the outgoing and incoming view carries it for free. */
type View = "chat" | `console:${ConsoleTab}`;

const viewOf = (tab: ConsoleTab): View => `console:${tab}`;

/** The overlay panel: one window that shows one view at a time and morphs between them.
 *
 *  Closed, it sits scaled at centre (summon/dismiss pop from the middle), except when the mode is
 *  `orb`, where `to-orb` parks it at the corner so minimize/maximize *travel* to and from the orb.
 *
 *  The chat view is never unmounted, only taken out of the layout flow: a half-typed draft, the
 *  history's scroll position, and the composer's focus all survive a trip to the console and back.
 *  The view being left behind is held for one morph, absolutely positioned so it cannot define the
 *  height the panel is easing to, and faded out over the one arriving. */
export function Panel(props: PanelProps) {
  const { state, open, themeName, mark, onOpenConsole, onCloseConsole } = props;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const view: View = state.consoleTab === null ? "chat" : viewOf(state.consoleTab);
  const leaving = useViewTransition(view, MORPH_MS);
  const panelRef = useRef<HTMLDivElement>(null);
  // Entering another view centres it, returning to the chat restores where the chat was, and any
  // size change inside a view pushes the top edge up from the pinned bottom. The view name carries
  // no session id on purpose: a different chat, or a new one, is the same view with other content
  // in it, so it resizes in place rather than jumping the panel to centre under the pencil.
  usePanelMotion(panelRef, open, view);

  const closed = state.mode === "orb" ? " to-orb" : "";
  // Two console tabs crossing is not a whole view arriving. The header and the tab strip are the
  // same chrome in both panes, at the same height, so the rise-and-sink that sells a view change
  // would show up as that shared chrome jittering (7px up on the pane leaving, 7px down on the one
  // arriving, measured 14px apart mid-fade in Chromium) while only the content under it changes.
  // Marked here rather than inside the console because it is a property of the TRANSITION, which is
  // the panel's business: only the panel knows which view is being left.
  const swap = leaving !== null && view !== "chat" && leaving !== "chat" ? " swap" : "";
  const classOf = (name: View) =>
    name === view ? `view${swap}` : name === leaving ? `view out${swap}` : "view gone";
  // A console tab is mounted while it is the view, and for one morph after it stops being one.
  const showing = (tab: ConsoleTab) => view === viewOf(tab) || leaving === viewOf(tab);

  return (
    <div
      ref={panelRef}
      className={`panel${open ? " open" : closed}`}
      role="dialog"
      aria-label="Cortex"
      aria-hidden={!open}
    >
      <div className="views">
        <div className={classOf("chat")} aria-hidden={view !== "chat"}>
          <ChatView {...props} />
        </div>
        {/* Both console tabs can be on screen at once, for exactly one morph: the one being left
            is still fading out over the one arriving. Mounted from the tab list rather than from
            two branches, so a third tab would be a name in that list and nothing here. */}
        {CONSOLE_TABS.filter((tab) => showing(tab)).map((tab) => (
          // Hidden from assistive tech the moment it stops being the view, like the chat above:
          // both panes are named "Console" and each carries a tab list and a tab panel, so without
          // this the tree would hold two of each for the length of a tab morph, and a reader
          // stepping through it would meet the tab it just left as a second, equal copy.
          <div key={tab} className={classOf(viewOf(tab))} aria-hidden={view !== viewOf(tab)}>
            <ConsoleView
              tab={tab}
              themeName={themeName}
              mark={mark}
              animated={!reduced}
              onPickTheme={props.onPickTheme}
              onPickMark={props.onPickMark}
              onSelectTab={onOpenConsole}
              onClose={onCloseConsole}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
