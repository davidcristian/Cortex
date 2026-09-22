import { useRef } from "react";

import type { DueReminder } from "../bridge/types";
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
  readonly onHoistSession: (sessionId: string, hoisted: boolean) => void;
  readonly onRespondConfirm: (confirmId: string, approved: boolean) => void;
  readonly onDismissReminder: (reminder: DueReminder) => void;
}

/** How long the outgoing view stays on screen. The panel's morph scales with the distance it
 *  travels, so this is imported from that scale's own ceiling: the fade outlasts every resize
 *  instead of ending inside one. */
const MORPH_MS = MAX_DURATION_MS;

/** A view of the panel. The console's tab is not part of the name: both tabs are mounted inside
 *  it, so switching tabs does not re-centre the panel or re-run the chrome's enter animation. */
type View = "chat" | "console";

const CONSOLE: View = "console";

/** The overlay panel: one window that shows one view at a time and morphs between them. The chat
 *  view is never unmounted, only taken out of the layout flow, so the composer's focus and caret
 *  survive a trip to the console and back. */
export function Panel(props: PanelProps) {
  const { state, open, themeName, mark, edge, onOpenConsole, onCloseConsole } = props;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const liquid = edge.waves.length > 0;
  const view: View = state.consoleTab === null ? "chat" : CONSOLE;
  const leaving = useViewTransition(view, MORPH_MS);
  const panelRef = useRef<HTMLDivElement>(null);
  // The chat's own column. A roll in the chrome is a sibling of the history, so its start event
  // never reaches that box and the log listens here instead. The console's column is a different
  // element, so a roll inside the console never reaches the log.
  const chatRef = useRef<HTMLDivElement>(null);
  // Which tab the console is showing, kept for the morph it spends on its way out. Its tab is
  // already null by then, so falling back to the first tab drew the appearance pane over the one
  // the user was looking at. Assigned during the render, so the closing render reads the right tab.
  const tab = useRef<ConsoleTab>("appearance");
  tab.current = state.consoleTab ?? tab.current;
  // The view name holds no session id: another chat is the same view with other content in it, so
  // the panel resizes in place rather than jumping to centre.
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
      // A dismissed panel is still mounted and was only `opacity: 0`, so Tab walked an invisible
      // panel and reached the reminder rows' buttons.
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
        {/* The view being left stays for one morph so the arriving one has something to fade
            against. It is out of flow and not clickable for those 380ms but was still tabbable, so
            `withdrawn` takes it out of the tab order for as long as it is out of the flow. */}
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
