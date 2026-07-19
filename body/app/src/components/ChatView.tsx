import { useEffect, useRef } from "react";

import type { MarkStyle } from "../mark/marks";
import { type OverlayState, isTurnActive } from "../overlay/overlayState";
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
  ShiftKey,
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

/** How close to the bottom (px) still counts as "reading the tail" for auto-scroll. */
const PIN_THRESHOLD_PX = 40;

/** Example prompts on the empty state; tapping one submits it. Real capabilities only. */
const EXAMPLE_PROMPTS = ["Summarize my unread email", "Remind me to stretch in 20 minutes"];

/** The panel's resting view: header, the roll-open sections, the scrolling history, the composer,
 *  and the shortcut hints. The history follows the stream (auto-scroll) unless the reader has
 *  scrolled up. The switcher list and the reminder stack roll open and shut through `Collapse`, so
 *  the panel's own height follows them instead of jumping and then catching up. */
export function ChatView({
  state,
  open,
  dark,
  mark,
  onToggleSettings,
  onToggleTheme,
  onSubmit,
  onStop,
  onDismiss,
  onNewChat,
  onToggleSwitcher,
  onToggleSheet,
  onSelectSession,
  onRenameSession,
  onDeleteSession,
  onPinSession,
  onRespondConfirm,
  onDismissReminder,
}: ChatViewProps) {
  // The history is always mounted with the view, so the ref is set before any effect runs.
  const historyRef = useRef<HTMLDivElement>(null!);
  const pinned = useRef(true);

  const onHistoryScroll = () => {
    const el = historyRef.current;
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight <= PIN_THRESHOLD_PX;
  };

  // Follow the stream: each message change (and the approval card) scrolls the tail into view,
  // unless the reader has scrolled up to read (then their place holds until they return).
  useEffect(() => {
    if (pinned.current) {
      const el = historyRef.current;
      el.scrollTop = el.scrollHeight;
    }
  }, [state.messages, state.pendingConfirm]);

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return (
    <>
      <header className="head">
        <LinkDot link={state.link} />
        <CaptureDot capturing={state.capturing} />
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
      <Collapse open={state.reminders.length > 0}>
        <Reminders
          reminders={state.reminders}
          currentId={state.sessionId}
          onDismiss={onDismissReminder}
          onOpen={onSelectSession}
        />
      </Collapse>
      <div className="history" ref={historyRef} onScroll={onHistoryScroll}>
        {state.messages.length === 0 ? (
          <div className="empty">
            <button
              className="markbtn"
              onClick={onToggleSettings}
              aria-label={`Mark: ${mark.label}. Open settings`}
              type="button"
            >
              <BubbleMark style={mark} size={54} idPrefix="empty" animated={!reduced} />
            </button>
            <p className="empty-line">Ask me anything</p>
            <div className="empty-chips">
              {EXAMPLE_PROMPTS.map((prompt) => (
                <button key={prompt} className="echip" onClick={() => onSubmit(prompt)} type="button">
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
      <Composer busy={isTurnActive(state)} active={open} onSubmit={onSubmit} onStop={onStop} />
      {/* Esc is not listed here: the strip is a convenience, it had run out of room once the
          settings button joined it, and Esc-to-dismiss is the most guessable of the five. The
          shortcuts view next to it still lists every binding, that one being the complete list. */}
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
        <button className="qbtn" onClick={onToggleSettings} aria-label="Settings" type="button">
          <b className="key">
            <SlidersIcon />
          </b>
        </button>
        <button className="qbtn" onClick={onToggleSheet} aria-label="Shortcuts" type="button">
          <b>?</b>
        </button>
      </div>
    </>
  );
}
