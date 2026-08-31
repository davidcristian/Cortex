import { type RefObject, useRef } from "react";

import type { DueReminder } from "../bridge/types";
import { caretKey, heir, useRowCaret } from "../overlay/rowCaret";
import { usePresence } from "../overlay/usePresence";
import { withdrawn } from "../overlay/withdrawn";
import { Collapse } from "./Collapse";
import { BellIcon, CheckIcon } from "./icons";
import { relativeTime } from "./relativeTime";

interface RemindersProps {
  readonly reminders: readonly DueReminder[];
  readonly currentId: string;
  /**
   * Where the caret goes when the last reminder is acked, the one case this stack cannot handle
   * from inside itself: the section is removed with its last row, so there is no list left to keep
   * the caret in.
   */
  readonly anchor: RefObject<HTMLElement | null>;
  readonly onDismiss: (reminderId: string) => void;
  readonly onOpen: (sessionId: string) => void;
}

/** Whether the row can offer its origin chat. */
function canOpen(reminder: DueReminder, currentId: string): boolean {
  return reminder.sessionId !== "" && reminder.sessionId !== currentId;
}

/**
 * The due-reminder stack (ADR-0025): what fired while the overlay was away, sitting above the
 * history and outside the scrolling log so that reading the conversation cannot move it out of
 * view.
 */
export function Reminders({
  reminders,
  currentId,
  anchor,
  onDismiss,
  onOpen,
}: RemindersProps) {
  const now = Date.now();
  const stack = usePresence(reminders, (reminder) => reminder.reminderId);
  const list = useRef<HTMLUListElement>(null);
  const caret = useRowCaret(list, anchor);
  const ack = (reminderId: string): void => {
    onDismiss(reminderId);
    caret(caretKey("ack", heir(reminders.map((held) => held.reminderId), reminderId)));
  };
  return (
    <ul className="reminders" aria-label="Due reminders" ref={list}>
      {stack.entries.map(({ key, item: reminder, leaving }) => (
        <li key={key} className="reminder-slot" {...withdrawn(leaving)}>
          <Collapse open={!leaving} onClosed={() => stack.released(key)}>
            <div className="reminder">
              <span className="reminder-mark" aria-hidden="true">
                <BellIcon />
              </span>
              <span className="reminder-body">
                <span className="reminder-text">{reminder.text}</span>
                {/* Rendered only when it has content. With the timestamp moved to the side column,
                    a reminder that is one-shot, untainted and already in the chat on screen has
                    nothing for this line, and an empty one would still take its top margin. */}
                {reminder.recurring || reminder.tainted || canOpen(reminder, currentId) ? (
                  <span className="reminder-meta">
                    {/* The control comes before the badges, because it is the only actionable item
                        on the line and the badges only describe the row. This keeps it at the same
                        x down the whole stack rather than shifted by how many badges a row has. */}
                    {canOpen(reminder, currentId) ? (
                      <button
                        type="button"
                        className="reminder-open"
                        onClick={() => onOpen(reminder.sessionId)}
                      >
                        open chat
                      </button>
                    ) : null}
                    {reminder.recurring ? (
                      <span className="reminder-tag">repeats</span>
                    ) : null}
                    {reminder.tainted ? (
                      <span className="reminder-tag untrusted">untrusted source</span>
                    ) : null}
                  </span>
                ) : null}
              </span>
              <span className="reminder-side">
                <button
                  type="button"
                  className="reminder-ack"
                  data-caret={caretKey("ack", reminder.reminderId)}
                  aria-label="Dismiss reminder"
                  onClick={() => ack(reminder.reminderId)}
                >
                  <CheckIcon />
                </button>
                <span className="reminder-time">
                  {relativeTime(reminder.firedAtUnixMs, now)}
                </span>
              </span>
            </div>
          </Collapse>
        </li>
      ))}
    </ul>
  );
}
