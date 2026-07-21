import { useRef } from "react";

import type { MarkStyle } from "../mark/marks";
import type { ConsoleTab, OverlayState } from "../overlay/overlayState";
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

/** How long the outgoing view stays on screen. */
const MORPH_MS = MAX_DURATION_MS;

/** A view of the panel. */
type View = "chat" | "console";

const CONSOLE: View = "console";

/** The overlay panel: one window that shows one view at a time and morphs between them. */
export function Panel(props: PanelProps) {
  const { state, open, themeName, mark, onOpenConsole, onCloseConsole } = props;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
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
      className={`panel${open ? " open" : closed}`}
      role="dialog"
      aria-label="Cortex"
      aria-hidden={!open}
    >
      <div className="views">
        <div className={classOf("chat")} aria-hidden={view !== "chat"}>
          <ChatView {...props} />
        </div>
        {view === CONSOLE || leaving === CONSOLE ? (
          <div className={classOf(CONSOLE)} aria-hidden={view !== CONSOLE}>
            <ConsoleView
              tab={tab.current}
              themeName={themeName}
              mark={mark}
              animated={!reduced}
              onPickTheme={props.onPickTheme}
              onPickMark={props.onPickMark}
              onSelectTab={onOpenConsole}
              onClose={onCloseConsole}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
