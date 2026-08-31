import { useRef } from "react";

import type { EdgeStyle } from "../edge/edges";
import type { MarkStyle } from "../mark/marks";
import { type ConsoleTab, type OverlayState, isTurnActive } from "../overlay/overlayState";
import { MAX_DURATION_MS } from "../overlay/panelGeometry";
import { usePanelMotion } from "../overlay/usePanelMotion";
import { useViewTransition } from "../overlay/useViewTransition";
import { withdrawn } from "../overlay/withdrawn";
import { ChatView } from "./ChatView";
import { ConsoleView } from "./ConsoleView";
import { PanelEdge } from "./PanelEdge";

interface PanelProps {
  readonly state: OverlayState;
  readonly open: boolean;
  readonly dark: boolean;
  readonly mark: MarkStyle;
  /** The window's edge style (ADR-0036): Still leaves the panel's own surface as it is, while a
   *  liquid style draws that surface through the `PanelEdge` layers. */
  readonly edge: EdgeStyle;
  /** The chosen theme name, or `null` while following the system scheme (the view shows it). */
  readonly themeName: string | null;
  readonly onPickTheme: (name: string | null) => void;
  readonly onPickMark: (name: string) => void;
  readonly onPickEdge: (name: string) => void;
  /** Open or close one console tab from its opener in the hint strip (the sliders, the ?). */
  readonly onToggleConsole: (tab: ConsoleTab) => void;
  /** Switch tabs from the strip inside the console; showing the tab already up is a no-op. */
  readonly onOpenConsole: (tab: ConsoleTab) => void;
  readonly onCloseConsole: () => void;
  readonly onToggleTheme: () => void;
  readonly onSubmit: (text: string) => void;
  /** Park the composer's field under the chat on screen, keystroke by keystroke (`drafts.ts`). */
  readonly onDraft: (text: string) => void;
  readonly onStop: () => void;
  readonly onDismiss: () => void;
  readonly onNewChat: () => void;
  readonly onToggleSwitcher: () => void;
  /** Load a chat, announced or not depending on which control opened it (`overlay/notice.ts`). */
  readonly onSelectSession: (sessionId: string, announce: boolean) => void;
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

/** A view of the panel. The console's tab is deliberately not part of the name: both tabs are
 *  mounted inside it, so switching tabs is not a view change, does not re-centre the panel, and
 *  does not re-run the chrome's enter animation. The first version made each tab a view of its own,
 *  which made the panel jump 12px between two tabs that differ by that much and faded the header
 *  and the back chevron out and in around the only content that was changing.
 *
 *  A tab change can still resize the panel, and `TAB_SPREAD_PX` in `ConsoleView` says when: tabs
 *  within it share the taller one's height, tabs beyond it each take their own and the panel
 *  morphs, which is a resize inside one view rather than a view change. */
type View = "chat" | "console";

const CONSOLE: View = "console";

/** The overlay panel: one window that shows one view at a time and morphs between them.
 *
 *  Closed, it sits scaled at centre (summon/dismiss pop from the middle), except when the mode is
 *  `orb`, where `to-orb` parks it at the corner so minimize/maximize *travel* to and from the orb.
 *
 *  The chat view is never unmounted, only taken out of the layout flow, so the composer's focus and
 *  its field survive a trip to the console and back (the draft would survive an unmount too, being
 *  state above this, but the caret would not). The view being left behind is held
 *  for one morph, absolutely positioned so it cannot define the height the panel is easing to, and
 *  faded out over the one arriving. The history's scroll position is the one thing being out of the
 *  flow does lose, so `ChatView` records it and restores it. */
export function Panel(props: PanelProps) {
  const { state, open, themeName, mark, edge, onOpenConsole, onCloseConsole } = props;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // A style with no waves is Still, which mounts no edge layers at all: the panel keeps its own
  // surface and costs nothing per frame.
  const liquid = edge.waves.length > 0;
  const view: View = state.consoleTab === null ? "chat" : CONSOLE;
  const leaving = useViewTransition(view, MORPH_MS);
  const panelRef = useRef<HTMLDivElement>(null);
  // The chat's own column, handed to the view inside it. A roll in the chrome (the switcher list,
  // the reminder stack, a row leaving either of them) is a sibling of the history and its start
  // event never reaches that box, so the log listens here instead (`useLogScroll`). The console's
  // column is deliberately a different element, so a roll inside the console never reaches the log.
  const chatRef = useRef<HTMLDivElement>(null);
  // Which tab the console is showing, kept for the morph it spends on its way out. The console is
  // still mounted then and its tab is already null, so falling back to the first tab drew the
  // appearance pane over the one the user was looking at: leaving from the shortcuts, the
  // appearance tab appeared for the length of the fade and left with it. Assigned during the
  // render, so it holds the right tab by the time the render that closed the console reads it.
  const tab = useRef<ConsoleTab>("appearance");
  tab.current = state.consoleTab ?? tab.current;
  // Entering another view centres it, returning to the chat restores where the chat was, and any
  // size change inside a view pushes the top edge up from the pinned bottom. The view name carries
  // no session id on purpose: a different chat, or a new one, is the same view with other content
  // in it, so it resizes in place rather than jumping the panel to centre under the pencil.
  usePanelMotion(panelRef, open, view);

  const closed = state.mode === "orb" ? " to-orb" : "";
  const classOf = (name: View) =>
    name === view ? "view" : name === leaving ? "view out" : "view gone";

  return (
    <div
      ref={panelRef}
      className={`panel${liquid ? " edge-live" : ""}${open ? " open" : closed}`}
      role="dialog"
      aria-label="Cortex"
      // A dismissed panel is still mounted (its `open` class is what animates the way out and the
      // way back in) and was `opacity: 0` with nothing taking it out of the tab order, so the tab
      // key walked an invisible panel: measured in Chromium at 900x900, Esc to the orb and then six
      // presses of Tab reached the two reminder rows' buttons three times over, every one of them
      // under this `aria-hidden`. The panel is the outermost of the three places the overlay holds
      // something mounted that is not on screen, and it gets the same rule as the other two.
      {...withdrawn(!open)}
    >
      {liquid ? (
        <PanelEdge
          style={edge}
          working={isTurnActive(state)}
          animated={!reduced}
          idPrefix="panel-edge"
        />
      ) : null}
      <div className="views">
        {/* The view being left is held for one morph so it has something to fade against, and for
            that morph it is `.out`: out of flow, not painted at full opacity, not clickable. It was
            still tabbable, though, and the fade is 380ms long: measured in Chromium at 900x900,
            leaving the console for the chat and then pressing Tab reached the back chevron and both
            faces of the strip inside the pane on its way out, and then the body. `withdrawn` takes
            the whole pane out of the tab order for exactly as long as it is out of the tree's. */}
        <div className={classOf("chat")} ref={chatRef} {...withdrawn(view !== "chat")}>
          <ChatView {...props} column={chatRef} />
        </div>
        {view === CONSOLE || leaving === CONSOLE ? (
          <div className={classOf(CONSOLE)} {...withdrawn(view !== CONSOLE)}>
            <ConsoleView
              tab={tab.current}
              themeName={themeName}
              mark={mark}
              edge={edge}
              animated={!reduced}
              onPickTheme={props.onPickTheme}
              onPickMark={props.onPickMark}
              onPickEdge={props.onPickEdge}
              onSelectTab={onOpenConsole}
              onClose={onCloseConsole}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
