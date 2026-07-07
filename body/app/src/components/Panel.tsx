import { type OverlayState, isTurnActive } from "../overlay/overlayState";
import { Composer } from "./Composer";
import { ChatsIcon, DownArrowKey, PencilIcon, ReturnKey, ShiftKey, TuckIcon, UpArrowKey } from "./icons";
import { Message } from "./Message";
import { SessionList } from "./SessionList";
import { ThemeIcon } from "./ThemeIcon";

interface PanelProps {
  readonly state: OverlayState;
  readonly open: boolean;
  readonly dark: boolean;
  readonly onToggleTheme: () => void;
  readonly onSubmit: (text: string) => void;
  readonly onStop: () => void;
  readonly onDismiss: () => void;
  readonly onNewChat: () => void;
  readonly onToggleSwitcher: () => void;
  readonly onSelectSession: (sessionId: string) => void;
}

/** The overlay panel: header, scrolling history, composer, and the shortcut hints. Closed, it
 *  sits scaled at center (summon/dismiss pop from the middle), except when the mode is `orb`,
 *  where `to-orb` parks it at the corner so minimize/maximize *travel* to and from the orb. */
export function Panel({
  state,
  open,
  dark,
  onToggleTheme,
  onSubmit,
  onStop,
  onDismiss,
  onNewChat,
  onToggleSwitcher,
  onSelectSession,
}: PanelProps) {
  const closed = state.mode === "orb" ? " to-orb" : "";
  return (
    <div className={`panel${open ? " open" : closed}`} role="dialog" aria-label="Cortex" aria-hidden={!open}>
      <header className="head">
        <span className="title">{state.title}</span>
        <button
          className="hbtn"
          onClick={onToggleSwitcher}
          aria-label="Recent chats"
          aria-expanded={state.switcherOpen}
          type="button"
        >
          <ChatsIcon />
        </button>
        <button className="hbtn" onClick={onToggleTheme} aria-label="Toggle theme" type="button">
          <ThemeIcon dark={dark} />
        </button>
        <button className="hbtn" onClick={onNewChat} aria-label="New chat" type="button">
          <PencilIcon />
        </button>
        <button className="hbtn" onClick={onDismiss} aria-label="Dismiss" type="button">
          <TuckIcon />
        </button>
      </header>
      {state.switcherOpen ? (
        <SessionList
          sessions={state.sessions}
          currentId={state.sessionId}
          onSelect={onSelectSession}
        />
      ) : null}
      <div className="history">
        {state.messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}
      </div>
      <Composer busy={isTurnActive(state)} onSubmit={onSubmit} onStop={onStop} />
      <div className="hints">
        <span>
          <b className="key">
            <ReturnKey />
          </b>{" "}
          send
        </span>
        <span>
          <b className="key">
            <ShiftKey />
            <ReturnKey />
          </b>{" "}
          newline
        </span>
        <span>
          <b>Esc</b> dismiss
        </span>
        <span>
          <b>Ctrl</b>
          <b>N</b> new
        </span>
        <span>
          <b>Ctrl</b>
          <b className="key">
            <UpArrowKey />
          </b>
          <b className="key">
            <DownArrowKey />
          </b>{" "}
          chats
        </span>
      </div>
    </div>
  );
}
