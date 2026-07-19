import { useRef } from "react";

import type { MarkStyle } from "../mark/marks";
import type { OverlayState } from "../overlay/overlayState";
import { usePanelMotion } from "../overlay/usePanelMotion";
import { useViewTransition } from "../overlay/useViewTransition";
import { ChatView } from "./ChatView";
import { SettingsView } from "./SettingsView";
import { ShortcutsView } from "./ShortcutsView";

interface PanelProps {
  readonly state: OverlayState;
  readonly open: boolean;
  readonly dark: boolean;
  readonly mark: MarkStyle;
  /** The chosen theme name, or `null` while following the system scheme (the view shows it). */
  readonly themeName: string | null;
  readonly onPickTheme: (name: string | null) => void;
  readonly onPickMark: (name: string) => void;
  readonly onToggleSettings: () => void;
  readonly onToggleTheme: () => void;
  readonly onSubmit: (text: string) => void;
  readonly onStop: () => void;
  readonly onDismiss: () => void;
  readonly onNewChat: () => void;
  readonly onToggleSwitcher: () => void;
  readonly onToggleSheet: () => void;
  readonly onSelectSession: (sessionId: string) => void;
  readonly onRenameSession: (sessionId: string, title: string) => void;
  readonly onDeleteSession: (sessionId: string) => void;
  readonly onPinSession: (sessionId: string, pinned: boolean) => void;
  readonly onRespondConfirm: (confirmId: string, approved: boolean) => void;
  readonly onDismissReminder: (reminderId: string) => void;
}

/** How long the outgoing view stays on screen; matches the panel's own morph in `usePanelMotion`
 *  so the fade and the resize finish together. */
const MORPH_MS = 380;

type View = "chat" | "shortcuts" | "settings";

/** The overlay panel: one window that shows one view at a time and morphs between them.
 *
 *  Closed, it sits scaled at centre (summon/dismiss pop from the middle), except when the mode is
 *  `orb`, where `to-orb` parks it at the corner so minimize/maximize *travel* to and from the orb.
 *
 *  The chat view is never unmounted, only taken out of the layout flow: a half-typed draft, the
 *  history's scroll position, and the composer's focus all survive a trip to settings and back. The
 *  view being left behind is held for one morph, absolutely positioned so it cannot define the
 *  height the panel is easing to, and faded out over the one arriving. */
export function Panel(props: PanelProps) {
  const { state, open, themeName, mark, onToggleSettings, onToggleSheet } = props;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const view: View = state.settingsOpen ? "settings" : state.sheetOpen ? "shortcuts" : "chat";
  const leaving = useViewTransition(view, MORPH_MS);
  const panelRef = useRef<HTMLDivElement>(null);
  // A view change re-centres the panel; growth inside a view pushes its top edge up instead.
  // The chat carries its session id, so opening a different chat re-centres for its new size too.
  usePanelMotion(panelRef, open, view === "chat" ? `chat:${state.sessionId}` : view);

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
        {view === "shortcuts" || leaving === "shortcuts" ? (
          <div className={classOf("shortcuts")}>
            <ShortcutsView onClose={onToggleSheet} />
          </div>
        ) : null}
        {view === "settings" || leaving === "settings" ? (
          <div className={classOf("settings")}>
            <SettingsView
              themeName={themeName}
              mark={mark}
              animated={!reduced}
              onPickTheme={props.onPickTheme}
              onPickMark={props.onPickMark}
              onClose={onToggleSettings}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
