import type { DueReminder } from "../bridge/types";
import { BellIcon, CheckIcon } from "./icons";
import { relativeTime } from "./relativeTime";

interface RemindersProps {
  readonly reminders: readonly DueReminder[];
  readonly currentId: string;
  readonly onDismiss: (reminderId: string) => void;
  readonly onOpen: (sessionId: string) => void;
}

/**
 * The due-reminder stack (ADR-0025): what fired while the overlay was away, sitting above the
 * history because it is delivery, not conversation. Dismissing acks it; opening loads the chat
 * the reminder was asked for, which is the context "stand-up in 10 minutes" leaves out.
 *
 * Every field is a plain text node and **nothing here is ever linkified**. Reminder text is the
 * one string the overlay displays that no output guardrail has inspected: it comes off a store
 * row, not a streamed reply, so ADR-0015's redaction never saw it. `tainted` badges the rows
 * whose text came from untrusted content; `recurring` says the series survives the dismissal.
 * The open control is a sibling of that text, never the text itself, so the clickable thing is
 * always app chrome with a fixed label rather than a string a stranger wrote.
 */
export function Reminders({ reminders, currentId, onDismiss, onOpen }: RemindersProps) {
  const now = Date.now();
  return (
    <ul className="reminders" aria-label="Due reminders">
      {reminders.map((reminder) => (
        <li key={reminder.reminderId} className="reminder">
          <span className="reminder-mark" aria-hidden="true">
            <BellIcon />
          </span>
          <span className="reminder-body">
            <span className="reminder-text">{reminder.text}</span>
            <span className="reminder-meta">
              <span>{relativeTime(reminder.firedAtUnixMs, now)}</span>
              {reminder.recurring ? <span className="reminder-tag">repeats</span> : null}
              {reminder.tainted ? (
                <span className="reminder-tag untrusted">untrusted source</span>
              ) : null}
              {/* No origin to go to (a session-less caller sends ""), and no point offering the
                  chat already on screen, where opening would only abandon whatever turn is
                  running in it. Absent rather than disabled: there is nothing to explain. */}
              {reminder.sessionId !== "" && reminder.sessionId !== currentId ? (
                <button
                  type="button"
                  className="reminder-open"
                  onClick={() => onOpen(reminder.sessionId)}
                >
                  open chat
                </button>
              ) : null}
            </span>
          </span>
          <button
            type="button"
            className="reminder-ack"
            aria-label="Dismiss reminder"
            onClick={() => onDismiss(reminder.reminderId)}
          >
            <CheckIcon />
          </button>
        </li>
      ))}
    </ul>
  );
}
