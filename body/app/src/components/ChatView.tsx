import { useEffect } from "react";

import type { MarkStyle } from "../mark/marks";
import { chatFloorRef } from "../overlay/measured";
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
  /** Load a chat. Whether the swap is announced belongs to the door, and this view holds both of
   *  them: a switcher row and a reminder's open control answer it differently (`notice.ts`). */
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
 *  and the shortcut hints. The history follows the stream (auto-scroll) unless the reader has
 *  scrolled up. The switcher list and the reminder stack roll open and shut through `Collapse`, so
 *  the panel's own height follows them instead of jumping and then catching up. */
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
        {/* The title opens the row and the two state indicators close it, immediately left of the
            button cluster. They sit together because they are one row of state, not two ornaments:
            splitting them would leave a lone capture ring beside the title that only ever appears
            mid-capture, so the header's left edge would gain and lose a dot per turn. Against the
            buttons they read as "what the panel currently is" next to "what you can do to it", and
            the title gets the corner to itself.

            The capture ring comes FIRST, which is a layout fact rather than a preference. The title
            is the row's only flexible item, so it absorbs every width change; a fixed item inserted
            directly against it costs the title 17px and moves nothing else. Put the ring on the far
            side of the connection dot instead and that dot, plus all four buttons, slide 17px left
            the moment a capture starts, mid-turn, while the user is watching the header. This way a
            capture beginning causes no motion anywhere in the row: the ring simply fades in, in
            space the title gives up. */}
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
          // Silent: the row IS the chat's name, so announcing would read the label back.
          onSelect={(sessionId) => onSelectSession(sessionId, false)}
          onRename={onRenameSession}
          onDelete={onDeleteSession}
          onPin={onPinSession}
        />
      </Collapse>
      {/* Keyed by the chat, because a session change is a content swap, not a section toggle.
          Minting a new chat over a conversation flips this stack open in the same render that
          empties the log, and rolled open there it fought the panel's own ease and read as a
          jump; remounted instead, it arrives with the empty state in the panel's one movement,
          exactly as it does coming back from the console. Within one chat the key holds still,
          so a reminder dismissed or arriving on the empty state still rolls. */}
      <Collapse
        aside
        key={state.sessionId}
        open={state.reminders.length > 0 && state.messages.length === 0}
      >
        <Reminders
          reminders={state.reminders}
          currentId={state.sessionId}
          onDismiss={onDismissReminder}
          // Announced: "open chat" names the act and not the chat, so the title is news.
          onOpen={(sessionId) => onSelectSession(sessionId, true)}
        />
      </Collapse>
      <div className="history" ref={log.ref} onScroll={log.onScroll}>
        {/* Everything the history holds lives in one inner column, `.log`, because the floor that
            stops the first send from shrinking the panel (its `min-height`, which is `--chat-floor`
            measured off the empty state below) has to sit on the CONTENT rather than on the scroll
            box. A floor on `.history` itself cannot yield: with the switcher and the reminder stack
            both open at the body's 720px window there is 76px left for the history, and a box that
            refuses to go below 195px there pushes the composer and the hint strip out past the
            panel's own clipped edge (measured in Chromium before this was written). Floored content
            just scrolls instead.

            `bare` says the log holds the empty state and nothing else, which is the one case where
            the column may be SHORTER than its content: an opening screen that scrolls is a wrong
            thing to have made, so it shrinks and stays centred instead (`.log.bare`). It is asked
            of the same two pieces of state the empty state itself is rendered from, so the class
            and the child can never disagree. */}
        <div className={`log${state.messages.length === 0 && state.pendingConfirm === null ? " bare" : ""}`}>
          {state.messages.length === 0 ? (
            // The ref is that floor, measured: this element stands for the whole life of an empty
            // chat and leaves as the first message lands (overlay/measured.ts).
            <div className="empty" ref={chatFloorRef}>
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
          {/* The whisper's drain outlives the turn's last render (ADR-0037), so a streamed
              bubble reports its growth and the tail pin answers exactly as it does for a new
              message: pinned readers follow, a reader who scrolled up holds their place. */}
          {state.messages.map((message) => (
            <Message key={message.id} message={message} onGrow={log.toTail} />
          ))}
          {state.pendingConfirm !== null ? (
            <ConfirmCard confirm={state.pendingConfirm} onRespond={onRespondConfirm} />
          ) : null}
        </div>
      </div>
      {/* The pill's growth is the log's loss: they are flex siblings and the log is the one that
          yields, so a draft that restacks or wraps takes the height out of the window above it
          while the engine leaves `scrollTop` where it was. Measured at a 720px window with the
          panel at its ceiling, a two-line draft left the newest reply 52px below the visible edge,
          clipped mid-line, and a draft at the field's own ceiling 122px. The reader is answering
          that reply, so it is exactly the thing that must not slide away under them. */}
      {/* The chat is only the ACTIVE view while no console tab is up, and the field takes focus on
          that rising edge. So coming back from the console puts the caret back in the composer
          (with the draft and its selection intact, since this field is never unmounted) instead of
          leaving focus on a tab strip that is fading out, which is where the click that opened the
          console left it and which the browser is about to display:none out from under it. */}
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
        {/* Shift and Return are two caps, not one cap holding two glyphs: every other hint here
            already separates its keys, and the console's shortcut list separates all of them, so a
            single cap made this the one place a chord read as one key.

            Shift is SPELLED OUT, like Ctrl and Alt beside it. Its glyph is the one modifier with a
            drawing, so drawn it was the only modifier on the row you had to recognise rather than
            read, sitting against three that are words. The drawn glyphs left are the keys that have
            no name worth writing: return, and the two cycle arrows. */}
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
        {/* Two doors into the one console, each landing on the tab it names: the sliders on
            appearance, the ? on the shortcut list. A press here is always an open, because the
            console is a view and replaces this one outright (`.view.gone` is `display: none`), so
            neither button is reachable while it is up. They still dispatch the toggle rather than
            the open, so that the strip and the ? KEY, which IS live inside the console and is the
            binding that can close it that way, stay one behaviour with one name. */}
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
