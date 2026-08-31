import { type RefObject, useEffect, useRef } from "react";

import type { MarkStyle } from "../mark/marks";
import { chatFloorRef } from "../overlay/measured";
import { RECENT_CHATS } from "../overlay/notice";
import { type ConsoleTab, type OverlayState, draftOf, isTurnActive } from "../overlay/overlayState";
import { handOff } from "../overlay/sectionCaret";
import { useLogScroll } from "../overlay/useLogScroll";
import { BubbleMark } from "./BubbleMark";
import { CaptureDot } from "./CaptureDot";
import { Collapse } from "./Collapse";
import { Composer } from "./Composer";
import { ConfirmCard } from "./ConfirmCard";
import { HintStrip } from "./HintStrip";
import { ChatsIcon, PencilIcon, TuckIcon } from "./icons";
import { LinkDot } from "./LinkDot";
import { Message } from "./Message";
import { Reminders } from "./Reminders";
import { SessionList } from "./SessionList";
import { ThemeIcon } from "./ThemeIcon";

export interface ChatViewProps {
  readonly state: OverlayState;
  /** The column the panel renders this view into, where the log listens for a roll in the chrome. */
  readonly column: RefObject<HTMLElement | null>;
  readonly open: boolean;
  readonly dark: boolean;
  readonly mark: MarkStyle;
  /** Open (or close again) one console tab: each opener in the hint strip owns its own tab. */
  readonly onToggleConsole: (tab: ConsoleTab) => void;
  readonly onToggleTheme: () => void;
  readonly onSubmit: (text: string) => void;
  /** Park the composer's field under the chat on screen, keystroke by keystroke (`drafts.ts`). */
  readonly onDraft: (text: string) => void;
  readonly onStop: () => void;
  readonly onDismiss: () => void;
  readonly onNewChat: () => void;
  readonly onToggleSwitcher: () => void;
  /** Load a chat. Whether the swap is announced depends on which control opened it, and this view
   *  holds both: a switcher row passes false and a reminder's open control passes true
   *  (`notice.ts`). */
  readonly onSelectSession: (sessionId: string, announce: boolean) => void;
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
  column,
  open,
  dark,
  mark,
  onToggleConsole,
  onToggleTheme,
  onSubmit,
  onDraft,
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
  // The chat is the view on screen while no console tab is up, and a view change is the one thing
  // the log's scroll position cannot survive on its own (`useLogScroll`).
  const showing = state.consoleTab === null;
  const log = useLogScroll(showing, column);

  const chatsButton = useRef<HTMLButtonElement>(null);
  const field = useRef<HTMLTextAreaElement>(null!);

  // Follow the stream: each message change (and the approval card) scrolls the tail into view,
  // unless the reader has scrolled up to read (then their place holds until they return).
  useEffect(log.toTail, [log.toTail, state.messages, state.pendingConfirm]);

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return (
    <>
      <header className="head">
        <span className="title">{state.title}</span>
        <CaptureDot claim={state.capture} />
        <LinkDot link={state.link} />
        <button
          className="hbtn"
          ref={chatsButton}
          onClick={onToggleSwitcher}
          aria-label={RECENT_CHATS}
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
          // The list places the caret for its own closing as well as for its own rows, and both
          // land on the anchor below (`overlay/sectionCaret.ts`). `arrival` is how it skips the
          // closings that are really chat swaps.
          open={state.switcherOpen}
          arrival={state.arrival}
          anchor={chatsButton}
          // Not announced: the row's own label is the chat's name, so announcing would read it back.
          onSelect={(sessionId) => onSelectSession(sessionId, false)}
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
          anchor={field}
          onDismiss={onDismissReminder}
          // Announced: the control is labelled "open chat" rather than with the chat's name, so the
          // title the reader lands on has not been read out yet.
          onOpen={(sessionId) => onSelectSession(sessionId, true)}
        />
      </Collapse>
      <div className="history" ref={log.ref} onScroll={log.onScroll}>
        <div className={`log${state.messages.length === 0 && state.pendingConfirm === null ? " bare" : ""}`}>
          {state.messages.length === 0 ? (
            // The floor is measured off this element, which is present for the whole life of an
            // empty chat and is removed as the first message lands (overlay/measured.ts).
            <div className="empty" ref={chatFloorRef}>
              <button
                className="markbtn"
                onClick={() => onToggleConsole("appearance")}
                // Named for where it lands, the console's appearance tab. The settings sheet this
                // used to open is gone, and an accessible name is the one place a stale view name
                // would still be read out after a rename.
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
                    onClick={() => {
                      onSubmit(prompt);
                      handOff(field);
                    }}
                    type="button"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {/* The whisper's drain outlives the turn's last render (ADR-0037), so a streamed bubble
              reports its growth and the tail pin responds as it does for a new message: a pinned
              reader follows, and a reader who scrolled up holds their place. */}
          {state.messages.map((message) => (
            <Message key={message.id} message={message} onGrow={log.toTail} />
          ))}
          {state.pendingConfirm !== null ? (
            <ConfirmCard confirm={state.pendingConfirm} onRespond={onRespondConfirm} />
          ) : null}
        </div>
      </div>
      <Composer
        field={field}
        busy={isTurnActive(state)}
        draft={draftOf(state.drafts, state.sessionId)}
        arrival={open && showing ? state.arrival : null}
        onSubmit={onSubmit}
        onDraft={onDraft}
        onStop={onStop}
        onResize={log.toTail}
      />
      <HintStrip onToggleConsole={onToggleConsole} />
    </>
  );
}
