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
 */
export function Reminders({
  reminders,
  currentId,
  onDismiss,
  onOpen,
}: RemindersProps) {
  const now = Date.now();
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
