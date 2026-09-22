import { type RefObject, useEffect, useRef } from "react";

import type { DueReminder } from "../bridge/types";
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
  /** The column the panel renders this view into, where the log listens for a roll in the
   *  chrome. */
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
  /** Load a chat. `announce` decides whether the live region says which chat arrived. */
  readonly onSelectSession: (sessionId: string, announce: boolean) => void;
  readonly onRenameSession: (sessionId: string, title: string) => void;
  readonly onDeleteSession: (sessionId: string) => void;
  readonly onHoistSession: (sessionId: string, hoisted: boolean) => void;
  readonly onRespondConfirm: (confirmId: string, approved: boolean) => void;
  readonly onDismissReminder: (reminder: DueReminder) => void;
}

/** Example prompts on the empty state; tapping one submits it. */
const EXAMPLE_PROMPTS = ["Summarize my unread email", "Remind me to stretch in 20 minutes"];

/** The panel's resting view: header, the roll-open sections, the scrolling history, the composer,
 *  and the shortcut hints. The history follows the stream unless the reader has scrolled up. */
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
  onHoistSession,
  onRespondConfirm,
  onDismissReminder,
}: ChatViewProps) {
  const showing = state.consoleTab === null;
  const log = useLogScroll(showing, column);

  // Where each list sends the caret when it runs out of rows. Deleting the last other chat leaves
  // the switcher open and empty, so the caret goes back to the control that opened it; acking the
  // last reminder removes the whole stack, so the caret goes to the field.
  const chatsButton = useRef<HTMLButtonElement>(null);
  const field = useRef<HTMLTextAreaElement>(null!);

  useEffect(log.toTail, [log.toTail, state.messages, state.pendingConfirm]);

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return (
    <>
      <header className="head">
        {/* The capture ring comes before the connection dot for a layout reason: the title is the
            row's only flexible item, so a fixed item next to it costs the title 17px and moves
            nothing else, while on the far side the dot and all four buttons would slide left. */}
        <span className="title">{state.title}</span>
        <CaptureDot claim={state.capture} />
        <LinkDot link={state.link} />
        {/* `aria-expanded` is all this control says about the list, which is why the key
            announces what the list holds and this button does not: pressing the button reads the
            state back under the reader's own caret. Its name comes from one place for all three. */}
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
          open={state.switcherOpen}
          arrival={state.arrival}
          anchor={chatsButton}
          // Not announced: the row's label is the chat's name, so announcing would read it back.
          onSelect={(sessionId) => onSelectSession(sessionId, false)}
          onRename={onRenameSession}
          onDelete={onDeleteSession}
          onHoist={onHoistSession}
        />
      </Collapse>
      {/* Keyed by the chat, because a new chat is a content swap rather than a section toggle:
          rolling the stack open in the render that empties the log ran against the panel's own
          ease. Within one chat the key does not change, so a reminder arriving still rolls. */}
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
          // Announced: the control is labelled "open chat", not with the chat's name, so the
          // title the reader arrives on has not been read out yet.
          onOpen={(sessionId) => onSelectSession(sessionId, true)}
        />
      </Collapse>
      <div className="history" ref={log.ref} onScroll={log.onScroll}>
        {/* The history's floor (`--chat-floor`) is on this inner column, not on the scroll box: a
            floor on `.history` pushed the composer past the panel's clipped edge. `bare` lets the
            one case that holds only the empty state shrink, so an opening screen does not scroll. */}
        <div className={`log${state.messages.length === 0 && state.pendingConfirm === null ? " bare" : ""}`}>
          {state.messages.length === 0 ? (
            // The chat floor is measured off this element, which is there for the whole life of
            // an empty chat and goes away with the first message.
            <div className="empty" ref={chatFloorRef}>
              <button
                className="markbtn"
                onClick={() => onToggleConsole("appearance")}
                aria-label={`Mark: ${mark.label}. Open appearance`}
                type="button"
              >
                <BubbleMark style={mark} size={54} idPrefix="empty" animated={!reduced} />
              </button>
              <p className="empty-line">Ask me anything</p>
              {/* Pressing a chip unmounts it with the rest of the empty state, and it is in no
                  list with a next row to take the caret, so it hands the caret to the field. */}
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
          {/* The whisper drains after the turn's last render, so a streamed bubble reports its
              growth and the history follows it as it does a new message. */}
          {state.messages.map((message) => (
            <Message key={message.id} message={message} onGrow={log.toTail} />
          ))}
          {state.pendingConfirm !== null ? (
            <ConfirmCard confirm={state.pendingConfirm} onRespond={onRespondConfirm} />
          ) : null}
        </div>
      </div>
      {/* The composer takes focus on every change of conversation, so returning from the console
          puts the caret back in the draft rather than on a tab strip about to be hidden. */}
      {/* Null while the console is over the chat, so no focus moves behind it. */}
      <Composer
        field={field}
        busy={isTurnActive(state)}
        draft={draftOf(state.drafts, state.sessionId)}
        arrival={open && showing ? state.arrival : null}
        onSubmit={onSubmit}
        onDraft={onDraft}
        onStop={onStop}
        // Growing the pill shortens the log: they are flex siblings and the log yields, while the
        // engine leaves `scrollTop` where it was. At a 720px window a two-line draft left the
        // newest reply 52px below the visible edge, and a full field 122px.
        onResize={log.toTail}
      />
      <HintStrip onToggleConsole={onToggleConsole} />
    </>
  );
}
