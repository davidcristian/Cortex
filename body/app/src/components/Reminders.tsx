import type { DueReminder } from "../bridge/types";
import { usePresence } from "../overlay/usePresence";
import { Collapse } from "./Collapse";
import { BellIcon, CheckIcon } from "./icons";
import { relativeTime } from "./relativeTime";

interface RemindersProps {
  readonly reminders: readonly DueReminder[];
  readonly currentId: string;
  readonly onDismiss: (reminderId: string) => void;
  readonly onOpen: (sessionId: string) => void;
}

/** Whether the row can offer its origin chat. There is nothing to go to when a session-less
 *  caller sent it (""), and no point offering the chat already on screen, where opening would
 *  only abandon whatever turn is running in it. Absent rather than disabled: nothing to explain. */
function canOpen(reminder: DueReminder, currentId: string): boolean {
  return reminder.sessionId !== "" && reminder.sessionId !== currentId;
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
export function Reminders({
  reminders,
  currentId,
  onDismiss,
  onOpen,
}: RemindersProps) {
  const now = Date.now();
  // The ack leaves in the frame the check is pressed and the row it removes stays on screen for
  // the length of its own roll (`usePresence`), so the list upstream is honest immediately and the
  // exit is the only thing that lags. The first version of this held the ACK back instead, behind
  // a timer the roll's length long, which made a user's gesture wait on an animation: an unmount
  // inside those 300ms cancelled the timer and nothing was ever acked.
  const stack = usePresence(reminders, (reminder) => reminder.reminderId);
  return (
    <ul className="reminders" aria-label="Due reminders">
      {stack.entries.map(({ key, item: reminder, leaving }) => (
        // The `<li>` is outside the roll and the row inside it: a list whose items are wrapper
        // divs is not a list to a screen reader, and the hairline between two rows is drawn with
        // an adjacent-sibling rule that a wrapper in between would silently switch off.
        <li key={key} className="reminder-slot">
          <Collapse open={!leaving} onClosed={() => stack.released(key)}>
            <div className="reminder">
              <span className="reminder-mark" aria-hidden="true">
                <BellIcon />
              </span>
              <span className="reminder-body">
                <span className="reminder-text">{reminder.text}</span>
                {/* Only when it holds something. With the timestamp moved to the side column, a
                    reminder that is one-shot, untainted and already in the chat on screen has no
                    meta line at all, and an empty one would still spend its top margin. */}
                {reminder.recurring || reminder.tainted || canOpen(reminder, currentId) ? (
                  <span className="reminder-meta">
                    {/* The one control leads the badges that follow it: it is the thing you can DO
                        and they only describe the row, so it sits at one x down the whole stack
                        rather than being pushed along by however many badges a reminder carries. */}
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
              {/* The row's right column, the switcher's arrangement turned upright: what you can do
                  to the reminder on top, aligned to the title it belongs to, and when it fired
                  beneath it. The timestamp left the meta line because it is not one of the badges
                  describing the reminder; it is the row's other fact, and against the right edge it
                  stops the badges being read as a list that starts with a time. */}
              <span className="reminder-side">
                <button
                  type="button"
                  className="reminder-ack"
                  aria-label="Dismiss reminder"
                  onClick={() => onDismiss(reminder.reminderId)}
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
