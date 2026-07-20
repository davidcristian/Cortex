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

/** How long the outgoing view stays on screen. The panel's own morph in `usePanelMotion` scales
 *  with the distance it travels, so the fade is timed to that scale's own ceiling and imported from
 *  it rather than restated here: it outlasts every resize rather than ending inside one, and the
 *  view being left is never cut away mid-movement. */
const MORPH_MS = MAX_DURATION_MS;

/** A view of the panel. The console's tab is NOT part of the name: both tabs are mounted inside it,
 *  so switching tabs is not a view change, does not re-centre the panel, and does not re-run the
 *  chrome's enter animation. Making a tab a view of its own was the first shape, and it flinched:
 *  the panel jumped 12px between two tabs that differ by that much, and the header and the back
 *  chevron faded out and in around content that was the only thing actually changing.
 *
 *  A tab change can still resize the panel, and there is one number saying when (`TAB_SPREAD_PX` in
 *  `ConsoleView`): tabs within it share the taller one's height, tabs beyond it each get their own
 *  and the panel morphs, which is the ordinary growth-inside-a-view move and not a view change. */
type View = "chat" | "console";

const CONSOLE: View = "console";

/** The overlay panel: one window that shows one view at a time and morphs between them.
 *
 *  Closed, it sits scaled at centre (summon/dismiss pop from the middle), except when the mode is
 *  `orb`, where `to-orb` parks it at the corner so minimize/maximize *travel* to and from the orb.
 *
 *  The chat view is never unmounted, only taken out of the layout flow, so a half-typed draft and
 *  the composer's focus survive a trip to the console and back. The view being left behind is held
 *  for one morph, absolutely positioned so it cannot define the height the panel is easing to, and
 *  faded out over the one arriving. The history's scroll position is the one thing that does NOT
 *  come along for free: being out of the flow is exactly what loses it, so `ChatView` parks it and
 *  hands it back. */
export function Panel(props: PanelProps) {
  const { state, open, themeName, mark, onOpenConsole, onCloseConsole } = props;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const view: View = state.consoleTab === null ? "chat" : CONSOLE;
  const leaving = useViewTransition(view, MORPH_MS);
  const panelRef = useRef<HTMLDivElement>(null);
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
              tab={state.consoleTab ?? "appearance"}
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
