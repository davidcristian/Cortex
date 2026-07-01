import { type OverlayState, isTurnActive } from "../overlay/overlayState";
import { Composer } from "./Composer";
import { Message } from "./Message";

interface PanelProps {
  readonly state: OverlayState;
  readonly open: boolean;
  readonly dark: boolean;
  readonly onToggleTheme: () => void;
  readonly onSubmit: (text: string) => void;
  readonly onDismiss: () => void;
  readonly onNewChat: () => void;
}

/** The overlay panel: header, scrolling history, composer, and the shortcut hints. */
export function Panel({ state, open, dark, onToggleTheme, onSubmit, onDismiss, onNewChat }: PanelProps) {
  return (
    <div className={`panel${open ? " open" : ""}`} role="dialog" aria-label="Cortex" aria-hidden={!open}>
      <header className="head">
        <span className="dot" aria-hidden="true" />
        <span className="title">{state.title}</span>
        <button className="hbtn" onClick={onToggleTheme} aria-label="Toggle theme" type="button">
          {dark ? "☾" : "☀"}
        </button>
        <button className="hbtn" onClick={onNewChat} aria-label="New chat" type="button">
          +
        </button>
        <button className="hbtn" onClick={onDismiss} aria-label="Dismiss" type="button">
          ×
        </button>
      </header>
      <div className="history">
        {state.messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}
      </div>
      <Composer busy={isTurnActive(state)} onSubmit={onSubmit} />
      <div className="hints">
        <span>
          <b>⏎</b> send
        </span>
        <span>
          <b>⇧⏎</b> newline
        </span>
        <span>
          <b>Esc</b> dismiss
        </span>
        <span>
          <b>Ctrl+N</b> new
        </span>
      </div>
    </div>
  );
}
