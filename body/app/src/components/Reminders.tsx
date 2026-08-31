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
  /** Where the caret goes when the last reminder is acked, the one case this stack cannot handle
   *  from inside itself: the section is removed with its last row, so there is no list left to keep
   *  the caret in. The composer's field is what the reader is left with, delivery being over and a
   *  chat being what is underneath (`overlay/rowCaret.ts`). */
  readonly anchor: RefObject<HTMLElement | null>;
  readonly onDismiss: (reminderId: string) => void;
  readonly onOpen: (sessionId: string) => void;
}

/** Whether the row can offer its origin chat. There is nowhere to go when a session-less caller
 *  sent it (""), and no reason to offer the chat already on screen, where opening would abandon
 *  whatever turn is running in it. The control is omitted rather than disabled, since a disabled
 *  control would need an explanation. */
function canOpen(reminder: DueReminder, currentId: string): boolean {
  return reminder.sessionId !== "" && reminder.sessionId !== currentId;
}

/**
 * The due-reminder stack (ADR-0025): what fired while the overlay was away, sitting above the
 * history and outside the scrolling log so that reading the conversation cannot move it out of
 * view. Dismissing acks it; opening loads the chat the reminder was asked for, which supplies the
 * context a line like "stand-up in 10 minutes" leaves out.
 *
 * Every field is a plain text node and **nothing here is ever linkified**. Reminder text is the one
 * string the overlay displays that no output guardrail has inspected: it comes off a store row
 * rather than a streamed reply, so ADR-0015's redaction never saw it. `tainted` badges the rows
 * whose text came from untrusted content, and `recurring` says the series survives the dismissal.
 * The open control is a sibling of that text and never the text itself, so the clickable element is
 * always app chrome with a fixed label rather than a string someone else wrote.
 */
export function Reminders({
  reminders,
  currentId,
  anchor,
  onDismiss,
  onOpen,
}: RemindersProps) {
  const now = Date.now();
  // The ack is sent in the frame the check is pressed and the row it removes stays on screen for
  // the length of its own roll (`usePresence`), so the list upstream is correct immediately and
  // only the exit lags. The first version held the ack back instead, behind a timer as long as the
  // roll, which made a user's gesture wait on an animation: an unmount inside those 300ms cancelled
  // the timer and nothing was ever acked.
  const stack = usePresence(reminders, (reminder) => reminder.reminderId);
  const list = useRef<HTMLUListElement>(null);
  // The caret follows the ack down the stack (`overlay/rowCaret.ts`). Acking is the one gesture
  // here that removes its own control, and the reader usually has another ack to make, so the next
  // row's ack takes the caret and clearing what fired while the overlay was away is one key pressed
  // repeatedly rather than a walk back into the stack between reminders.
  const caret = useRowCaret(list, anchor);
  const ack = (reminderId: string): void => {
    onDismiss(reminderId);
    caret(caretKey("ack", heir(reminders.map((held) => held.reminderId), reminderId)));
  };
  return (
    <ul className="reminders" aria-label="Due reminders" ref={list}>
      {stack.entries.map(({ key, item: reminder, leaving }) => (
        // The `<li>` is outside the roll and the row inside it: a list whose items are wrapper
        // divs is not a list to a screen reader, and the hairline between two rows is drawn with
        // an adjacent-sibling rule that a wrapper in between would silently switch off.
        //
        // A leaving row is withdrawn for its exit, the same rule the switcher uses, because an
        // acked reminder is no longer a live control. Measured before this, its ack held focus for
        // the whole 300ms roll and its two controls stayed in the tab order behind the caret that
        // had already moved on, so Shift+Tab walked back into a reminder that was already answered.
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
              {/* The row's right column, which is the switcher's arrangement rotated: the ack on
                  top, aligned with the text it belongs to, and the fired time beneath it. The
                  timestamp left the meta line because it is not one of the badges describing the
                  reminder, and against the right edge it stops the badges reading as a list that
                  starts with a time. */}
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
