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

/** The panel's resting view: header, the roll-open sections, the scrolling history, the composer,
 *  and the shortcut hints. The history follows the stream unless the reader has scrolled up, and
 *  holds its place while a roll shortens its window (`overlay/logRide.ts`). The switcher list and
 *  the reminder stack roll through `Collapse`, so the panel's height follows them frame by frame. */
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

  // Where each list sends the caret when it has no row left to send it to. Both are lists whose
  // rows can be removed while the reader is inside them, and each keeps the caret among its own
  // rows while it has any (`overlay/rowCaret.ts`). This view holds the two controls that receive
  // the caret when a list runs out, because neither control belongs to the list itself.
  //
  // The two differ because what the reader is left with differs. Delete the last other chat and the
  // switcher is still open and empty, so the caret goes to the header control that opened it and
  // would close it again. Ack the last reminder and the stack is removed with it, leaving the
  // conversation underneath, whose caret belongs in the field a summon already lands in.
  //
  // The chats button receives the caret in two cases, the list emptying and the list closing
  // (`overlay/sectionCaret.ts`), which leave the same reader in the same place. The field receives
  // it in two as well: the stack's last ack, and an example chip below, whose press removes the
  // whole empty state.
  const chatsButton = useRef<HTMLButtonElement>(null);
  const field = useRef<HTMLTextAreaElement>(null!);

  // Follow the stream: each message change (and the approval card) scrolls the tail into view,
  // unless the reader has scrolled up to read (then their place holds until they return).
  useEffect(log.toTail, [log.toTail, state.messages, state.pendingConfirm]);

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return (
    <>
      <header className="head">
        {/* The title starts the row and the two state indicators end it, immediately left of the
            button cluster. They sit together as one group, because separating them would leave a
            lone capture ring beside the title that only appears mid-capture, so the header's left
            edge would gain and lose a dot every turn. Beside the buttons they read as what the panel
            currently is, next to what can be done to it, and the title keeps the corner.

            The capture ring comes first for a layout reason. The title is the row's only flexible
            item, so it absorbs every width change; a fixed item inserted directly against it costs
            the title 17px and moves nothing else. With the ring on the far side of the connection
            dot, that dot and all four buttons slide 17px left the moment a capture starts, mid-turn,
            while the user is watching the header. In this order a capture starting moves nothing:
            the ring fades in, in space the title gives up. */}
        <span className="title">{state.title}</span>
        <CaptureDot claim={state.capture} />
        <LinkDot link={state.link} />
        {/* `aria-expanded` is all this control says about the list, and measured, it was all the
            overlay said about it: opening the list by key moved no caret and raised no live region
            anywhere. So the key announces what the list holds and this button does not, since
            pressing the button already reads the state back under the reader's own caret
            (`overlay/notice.ts`). Its name is imported for the same reason the empty line's words
            are: the button, the list and the sentence render one name. */}
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
      {/* Keyed by the chat, because a session change is a content swap rather than a section
          toggle. Minting a new chat over a conversation opens this stack in the same render that
          empties the log, and rolling it open there ran against the panel's own ease and read as a
          jump. Remounted instead, it arrives with the empty state in the panel's one movement, as
          it does coming back from the console. Within one chat the key does not change, so a
          reminder dismissed or arriving on the empty state still rolls. */}
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
        {/* Everything the history holds lives in one inner column, `.log`, because the floor that
            stops the first send from shrinking the panel (its `min-height`, which is `--chat-floor`
            measured off the empty state below) has to sit on the content rather than on the scroll
            box. A floor on `.history` itself cannot shrink: with the switcher and the reminder
            stack both open at the body's 720px window there is 76px left for the history, and a box
            held at 195px there pushes the composer and the hint strip past the panel's own clipped
            edge (measured in Chromium before this was written). Floored content scrolls instead.

            `bare` marks the case where the log holds the empty state and nothing else, the one case
            where the column may be shorter than its content: an opening screen should not scroll,
            so it shrinks and stays centred (`.log.bare`). The class is computed from the same two
            pieces of state the empty state itself is rendered from, so the class and the child
            cannot disagree. */}
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
              {/* Pressing a chip unmounts it, because the empty state goes with the first message,
                  and it is the one such control that is not in a list with a next row to receive
                  the caret: measured at 900x900, pressing one left `document.activeElement` on
                  `<body>` at 39ms, removing the reminder stack above it in the same commit. It
                  passes the caret to the field, where the reply to the prompt it just sent gets
                  written and where the composer's own send leaves it
                  (`overlay/sectionCaret.ts`). */}
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
      {/* Growing the pill shortens the log: they are flex siblings and the log is the one that
          yields, so a draft that restacks or wraps takes the height out of the window above it
          while the engine leaves `scrollTop` where it was. Measured at a 720px window with the
          panel at its ceiling, a two-line draft left the newest reply 52px below the visible edge,
          clipped mid-line, and a draft at the field's own ceiling 122px. That reply is what the
          reader is answering, so it must not slide out of view. */}
      {/* The chat is the active view only while no console tab is up, so the composer is told which
          conversation it is sitting in only then, and null otherwise. It takes focus on every
          change: coming back from the console puts the caret back in the draft (intact, since this
          field is never unmounted) rather than on a tab strip the browser is about to display:none
          out from under it, and a chat arriving lands the caret in the conversation that arrived.
          The text that caret lands in is the arriving chat's own half-typed sentence, because the
          field renders this conversation's draft and so changes with the conversation
          (`overlay/drafts.ts`). */}
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
