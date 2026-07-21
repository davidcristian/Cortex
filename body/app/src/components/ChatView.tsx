import { useEffect } from "react";

import type { MarkStyle } from "../mark/marks";
import { type ConsoleTab, type OverlayState, isTurnActive } from "../overlay/overlayState";
import { useLogScroll } from "../overlay/useLogScroll";
import { BubbleMark } from "./BubbleMark";
import { CaptureDot } from "./CaptureDot";
import { Collapse } from "./Collapse";
import { Composer } from "./Composer";
import { ConfirmCard } from "./ConfirmCard";
import {
  ChatsIcon,
  DownArrowKey,
  PencilIcon,
  ReturnKey,
  SlidersIcon,
  TuckIcon,
  UpArrowKey,
} from "./icons";
import { LinkDot } from "./LinkDot";
import { Message } from "./Message";
import { Reminders } from "./Reminders";
import { SessionList } from "./SessionList";
import { ThemeIcon } from "./ThemeIcon";

export interface ChatViewProps {
  readonly state: OverlayState;
  readonly open: boolean;
  readonly dark: boolean;
  readonly mark: MarkStyle;
  /** Open (or close again) one console tab: each opener in the hint strip owns its own tab. */
  readonly onToggleConsole: (tab: ConsoleTab) => void;
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

/** Example prompts on the empty state; tapping one submits it. Real capabilities only. */
const EXAMPLE_PROMPTS = ["Summarize my unread email", "Remind me to stretch in 20 minutes"];

/**
 * The panel's resting view: header, the roll-open sections, the scrolling history, the composer,
 * and the shortcut hints.
 */
export function ChatView({
  state,
  open,
  dark,
  mark,
  onToggleConsole,
  onToggleTheme,
  onSubmit,
  onStop,
  onDismiss,
  onNewChat,
  onToggleSwitcher,
  onSelectSession,
  onRenameSession,
  onDeleteSession,
  onPinSession,
  onRespondConfirm,
  onDismissReminder,
}: ChatViewProps) {
  // The chat is the view on screen while no console tab is up, which is the one thing the log's
  // scroll position cannot look after itself through (`useLogScroll`).
  const showing = state.consoleTab === null;
  const log = useLogScroll(showing);

  // Follow the stream: each message change (and the approval card) scrolls the tail into view,
  // unless the reader has scrolled up to read (then their place holds until they return).
  useEffect(log.toTail, [log.toTail, state.messages, state.pendingConfirm]);

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return (
    <>
      <header className="head">
        <span className="title">{state.title}</span>
        <CaptureDot capturing={state.capturing} />
        <LinkDot link={state.link} />
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
      <Collapse open={state.switcherOpen}>
        <SessionList
          sessions={state.sessions}
          currentId={state.sessionId}
          onSelect={onSelectSession}
          onRename={onRenameSession}
          onDelete={onDeleteSession}
          onPin={onPinSession}
        />
      </Collapse>
      <Collapse
        aside
        key={state.sessionId}
        open={state.reminders.length > 0 && state.messages.length === 0}
      >
        <Reminders
          reminders={state.reminders}
          currentId={state.sessionId}
          onDismiss={onDismissReminder}
          onOpen={onSelectSession}
        />
      </Collapse>
      <div className="history" ref={log.ref} onScroll={log.onScroll}>
        <div className={`log${state.messages.length === 0 && state.pendingConfirm === null ? " bare" : ""}`}>
          {state.messages.length === 0 ? (
            <div className="empty">
              <button
                className="markbtn"
                onClick={() => onToggleConsole("appearance")}
                // Named for where it lands, which is the console's appearance tab: the settings
                // sheet this used to open is gone, and a label naming a view that no longer
                // exists is the one part of a rename a screen reader would still be reading out.
                aria-label={`Mark: ${mark.label}. Open appearance`}
                type="button"
              >
                <BubbleMark style={mark} size={54} idPrefix="empty" animated={!reduced} />
              </button>
              <p className="empty-line">Ask me anything</p>
              <div className="empty-chips">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    className="echip"
                    onClick={() => onSubmit(prompt)}
                    type="button"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {state.messages.map((message) => (
            <Message key={message.id} message={message} />
          ))}
          {state.pendingConfirm !== null ? (
            <ConfirmCard confirm={state.pendingConfirm} onRespond={onRespondConfirm} />
          ) : null}
        </div>
      </div>
      <Composer
        busy={isTurnActive(state)}
        active={open && showing}
        onSubmit={onSubmit}
        onStop={onStop}
        onResize={log.toTail}
      />
      {/* Esc is not listed here: the strip is a convenience, it had run out of room once the
          settings button joined it, and Esc-to-dismiss is the most guessable of the five. The
          console's shortcuts tab still lists every binding, that one being the complete list. */}
      <div className="hints">
        <span>
          <b className="key">
            <ReturnKey />
          </b>{" "}
          send
        </span>
        <span>
          <b>Shift</b>
          <b className="key">
            <ReturnKey />
          </b>{" "}
          new line
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
        <button
          className="qbtn"
          onClick={() => onToggleConsole("appearance")}
          aria-label="Settings"
          type="button"
        >
          <b className="key">
            <SlidersIcon />
          </b>
        </button>
        <button
          className="qbtn"
          onClick={() => onToggleConsole("shortcuts")}
          aria-label="Shortcuts"
          type="button"
        >
          <b>?</b>
        </button>
      </div>
    </>
  );
}
