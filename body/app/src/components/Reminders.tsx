import type { DueReminder } from "../bridge/types";
import { BellIcon, CheckIcon } from "./icons";
import { relativeTime } from "./relativeTime";

interface RemindersProps {
  readonly reminders: readonly DueReminder[];
  readonly onDismiss: (reminderId: string) => void;
}

/**
 * The due-reminder stack (ADR-0025): what fired while the overlay was away, sitting above the
 * history because it is delivery, not conversation. Dismissing acks it.
 *
 * Every field is a plain text node and **nothing here is ever linkified**. Reminder text is the
 * one string the overlay displays that no output guardrail has inspected: it comes off a store
 * row, not a streamed reply, so ADR-0015's redaction never saw it. `tainted` badges the rows
 * whose text came from untrusted content; `recurring` says the series survives the dismissal.
 */
export function Reminders({ reminders, onDismiss }: RemindersProps) {
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
