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
  /** Where the caret goes when the last reminder is acked, which is the one case this stack cannot
   *  answer from inside itself: the section goes with its last row, so there is no list left to
   *  keep the caret in. The composer's field is what the reader is left with, delivery being done
   *  and a chat being what is underneath it (`overlay/rowCaret.ts`). */
  readonly anchor: RefObject<HTMLElement | null>;
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
  anchor,
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
  const list = useRef<HTMLUListElement>(null);
  // The caret rides the ack down the stack (`overlay/rowCaret.ts`). Acking is the one gesture here
  // that takes its own control away, and the reader almost always has another to make: the next
  // row's ack takes the caret, so clearing what fired while the overlay was away is one key
  // pressed repeatedly rather than a walk back into the stack between reminders.
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
        // A leaving row is WITHDRAWN for its exit, which is the switcher's rule arriving here: an
        // acked reminder is not a live control. Measured at HEAD, its ack held focus for the whole
        // 300ms roll and its two controls stayed in the tab order behind the caret that had already
        // moved on, so Shift+Tab walked back into a reminder that was answered and gone.
        <li key={key} className="reminder-slot" {...withdrawn(leaving)}>
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
