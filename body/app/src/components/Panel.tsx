import { useEffect, useRef } from "react";

import { type OverlayState, isTurnActive } from "../overlay/overlayState";
import { useGrowthAnimation } from "../overlay/useGrowthAnimation";
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
import { CaptureDot } from "./CaptureDot";
import { LinkDot } from "./LinkDot";
import type { MarkStyle } from "../mark/marks";
import { BubbleMark } from "./BubbleMark";
import { Message } from "./Message";
import { Reminders } from "./Reminders";
import { SessionList } from "./SessionList";
import { SettingsSheet } from "./SettingsSheet";
import { ShortcutSheet } from "./ShortcutSheet";
import { ThemeIcon } from "./ThemeIcon";

interface PanelProps {
  readonly state: OverlayState;
  readonly open: boolean;
  readonly dark: boolean;
  readonly mark: MarkStyle;
  /** The chosen theme name, or `null` while following the system scheme (the sheet shows it). */
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

/** How close to the bottom (px) still counts as "reading the tail" for auto-scroll. */
const PIN_THRESHOLD_PX = 40;

/** Example prompts on the empty state; tapping one submits it. Real capabilities only. */
const EXAMPLE_PROMPTS = ["Summarize my unread email", "Remind me to stretch in 20 minutes"];

/** The overlay panel: header, scrolling history, composer, and the shortcut hints. Closed, it
 *  sits scaled at center (summon/dismiss pop from the middle), except when the mode is `orb`,
 *  where `to-orb` parks it at the corner so minimize/maximize *travel* to and from the orb.
 *  The history follows the stream (auto-scroll) unless the reader has scrolled up. */
export function Panel({
  state,
  open,
  dark,
  mark,
  themeName,
  onPickTheme,
  onPickMark,
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
}: PanelProps) {
  const closed = state.mode === "orb" ? " to-orb" : "";
  // The history is always mounted with the panel, so the ref is set before any effect runs.
  const historyRef = useRef<HTMLDivElement>(null!);
  const panelRef = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  // Anything that resizes the panel eases into place (see the hook): the panel is anchored by
  // its bottom edge in CSS, so what the eye sees is the top edge travelling up or down.
  useGrowthAnimation(panelRef, open);

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
    <div
      ref={panelRef}
      className={`panel${open ? " open" : closed}`}
      role="dialog"
      aria-label="Cortex"
      aria-hidden={!open}
    >
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
      {state.switcherOpen ? (
        <SessionList
          sessions={state.sessions}
          currentId={state.sessionId}
          onSelect={onSelectSession}
          onRename={onRenameSession}
          onDelete={onDeleteSession}
          onPin={onPinSession}
        />
      ) : null}
      {state.reminders.length > 0 ? (
        <Reminders
          reminders={state.reminders}
          currentId={state.sessionId}
          onDismiss={onDismissReminder}
          onOpen={onSelectSession}
        />
      ) : null}
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
          shortcut sheet next to it still lists every binding, that one being the complete list. */}
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
      {state.sheetOpen ? <ShortcutSheet onClose={onToggleSheet} /> : null}
      {state.settingsOpen ? (
        <SettingsSheet
          themeName={themeName}
          mark={mark}
          animated={!reduced}
          onPickTheme={onPickTheme}
          onPickMark={onPickMark}
          onClose={onToggleSettings}
        />
      ) : null}
    </div>
  );
}
