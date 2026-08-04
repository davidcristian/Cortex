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
  /** The window's edge style (ADR-0036): Still leaves the panel exactly as it was; a liquid
   *  style hands the panel's face to the `PanelEdge` layers. */
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
  readonly onStop: () => void;
  readonly onDismiss: () => void;
  readonly onNewChat: () => void;
  readonly onToggleSwitcher: () => void;
  /** Load a chat, announcing it or not by the door it came from (`overlay/notice.ts`). */
  readonly onSelectSession: (sessionId: string, announce: boolean) => void;
  readonly onRenameSession: (sessionId: string, title: string) => void;
  readonly onDeleteSession: (sessionId: string) => void;
  readonly onPinSession: (sessionId: string, pinned: boolean) => void;
  readonly onRespondConfirm: (confirmId: string, approved: boolean) => void;
  readonly onDismissReminder: (reminderId: string) => void;
}

/** How long the outgoing view stays on screen. */
const MORPH_MS = MAX_DURATION_MS;

/** A view of the panel. */
type View = "chat" | "console";

const CONSOLE: View = "console";

/** The overlay panel: one window that shows one view at a time and morphs between them. */
export function Panel(props: PanelProps) {
  const { state, open, themeName, mark, edge, onOpenConsole, onCloseConsole } = props;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // A style with no waves is Still, and Still mounts nothing: the panel keeps its own face and
  // pays nothing per frame, so the crisp choice is exactly the panel this feature found.
  const liquid = edge.waves.length > 0;
  const view: View = state.consoleTab === null ? "chat" : CONSOLE;
  const leaving = useViewTransition(view, MORPH_MS);
  const panelRef = useRef<HTMLDivElement>(null);
  const tab = useRef<ConsoleTab>("appearance");
  tab.current = state.consoleTab ?? tab.current;
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
        <div className={classOf("chat")} {...withdrawn(view !== "chat")}>
          <ChatView {...props} />
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
