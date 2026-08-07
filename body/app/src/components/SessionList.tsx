import { type RefObject, useRef, useState } from "react";

import type { SessionSummary } from "../bridge/types";
import { NO_OTHER_CHATS } from "../overlay/notice";
import { caretKey, heir, useRowCaret } from "../overlay/rowCaret";
import { usePresence } from "../overlay/usePresence";
import { useTravel } from "../overlay/useTravel";
import { withdrawn } from "../overlay/withdrawn";
import { Collapse } from "./Collapse";
import { type RowShape, SessionRow } from "./SessionRow";

interface SessionListProps {
  readonly sessions: readonly SessionSummary[];
  readonly currentId: string;
  /** Where the caret goes when this list has no row left to hand it to, which is the chat the
   *  reader just deleted their last other one from: the header control that opened the list. It
   *  is still on screen, it is what closes the list again, and it is the one control whose whole
   *  job is this list (`overlay/rowCaret.ts`). */
  readonly anchor: RefObject<HTMLElement | null>;
  readonly onSelect: (sessionId: string) => void;
  /** Rename a chat (ADR-0021 management addendum): submit a new label, or an empty one to
   *  clear a custom title back to the derived one. A user-only write. */
  readonly onRename: (sessionId: string, title: string) => void;
  /** Delete a chat (ADR-0021 management addendum): a destructive, irreversible user-only write.
   *  Called ONLY after this row's local "are you sure" confirm, so a stray click cannot delete. */
  readonly onDelete: (sessionId: string) => void;
  /** Pin or unpin a chat (ADR-0021 pinning addendum): a user-only write toggling `pinned`, so a
   *  pinned chat stays listed above the recency window. Fires immediately (no confirm needed). */
  readonly onPin: (sessionId: string, pinned: boolean) => void;
}

/** The switcher dropdown: recent chats with title, relative time, and a one-line preview, each
 *  with inline pin, rename, and delete affordances. Store-backed (ADR-0021); selecting one loads
 *  its history, pinning lifts it above the recency window, renaming writes its display title, and
 *  deleting removes it (behind a per-row confirm), the overlay re-listing to reflect each write.
 *  The brain returns pinned chats first (ADR-0021 pinning addendum), so the pinned group renders at
 *  the top; each pinned row carries a filled pin indicator, making the grouping legible. */
export function SessionList({
  sessions,
  currentId,
  anchor,
  onSelect,
  onRename,
  onDelete,
  onPin,
}: SessionListProps) {
  const now = Date.now();
  // Which row is being renamed (at most one), and its in-progress label. Local UI state only:
  // the committed title lives in the store, and the switcher re-lists to reflect it.
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  // Which row is awaiting a delete confirmation (at most one). Local UI state: the destructive
  // write fires only when the user confirms here, so a single stray click never deletes a chat.
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  // A deleted chat leaves `sessions` the moment the write lands, and the row it takes with it
  // stays on screen for the length of its own roll (`usePresence`, shared with the reminder
  // stack). Before this, the row was gone in the frame the delete resolved and everything under it
  // snapped up 50px into the hole; the panel does not move at all, so that snap was the whole of
  // what the eye saw. The hook holds no clock: `Collapse` reports the roll over and the row is
  // dropped then, which is what keeps the WRITE immediate and only the exit lagging.
  const stack = usePresence(sessions, (session) => session.sessionId);
  // And a row the list MOVES travels there. The brain lists pinned chats first and then by recency,
  // so pinning one regroups everything around it, and every row the regrouping touched used to be
  // at its new place in the frame the write landed (`overlay/useTravel.ts` has the trace and the
  // mechanism). Rows only: the empty line below is not one of them, and it has nowhere to go.
  const card = useRef<HTMLUListElement>(null);
  useTravel(card, ".switcher-slot");
  // AND THE CARET TRAVELS TOO. Every gesture below takes the control that fired it off the page,
  // and each hands the caret on rather than dropping it on `<body>` (`overlay/rowCaret.ts` carries
  // the rule and the measurements). After `useTravel`, so a row's new place is settled before
  // anything is focused inside it; neither cares, focus moving nothing and `preventScroll` keeping
  // it that way, and the order is the one that stays right if either ever does.
  const caret = useRowCaret(card, anchor);

  const startRename = (session: SessionSummary): void => {
    setRenamingId(session.sessionId);
    setDraft(session.title);
    // The editor is a control the reader is expected to type into at once, so it takes the caret
    // and the name it is standing in for comes selected with it.
    caret(caretKey("name", session.sessionId));
  };
  // Both ways out of an editor, and both give the caret back to the pencil that opened it: the
  // reader is where they were, on the row they were on, and the pencil's own label now reads the
  // name they just gave it.
  const endRename = (sessionId: string, commit: boolean): void => {
    if (commit) {
      onRename(sessionId, draft.trim());
    }
    setRenamingId(null);
    caret(caretKey("rename", sessionId));
  };
  const startDelete = (sessionId: string): void => {
    setConfirmingDeleteId(sessionId);
    caret(caretKey("keep", sessionId));
  };
  const cancelDelete = (sessionId: string): void => {
    setConfirmingDeleteId(null);
    caret(caretKey("delete", sessionId));
  };
  const confirmDelete = (sessionId: string): void => {
    onDelete(sessionId);
    setConfirmingDeleteId(null);
    if (sessionId === currentId) {
      // Deleting the chat on screen is a SWAP: a fresh one arrives in its place and takes the caret
      // to the composer with it (`sessionState.deleteSession`, `Composer`). Saying nothing here is
      // what lets that rule answer, rather than aiming the caret at a row first and having the
      // arriving chat pull it out of the list a moment later.
      return;
    }
    // Every other delete leaves the reader in the list they are managing, on the row that has just
    // moved into the gap, and on the same control they pressed to make the gap: deleting several
    // chats is then the one gesture repeated rather than a walk back into the list each time.
    caret(caretKey("delete", heir(sessions.map((session) => session.sessionId), sessionId)));
  };

  const shapeOf = (sessionId: string): RowShape => {
    if (sessionId === renamingId) {
      return "rename";
    }
    return sessionId === confirmingDeleteId ? "confirm" : "rest";
  };

  return (
    // The list is the list of composite rows it behaves like, and says so. It carried
    // `role="listbox"` once, which nothing under it satisfied: an option is a leaf and these rows
    // are four buttons each, so the container announced a listbox holding no options. Measured in
    // Chromium, the cost was not only the missing role. A `<li>` inside a listbox is not a
    // listitem, so every row came through as `none` and the boundaries a reader counts rows by
    // were gone, leaving twelve loose buttons in a list of nothing. Dropped, the implicit list and
    // listitem roles come back, `aria-label` names the list, and this is the reminder stack's
    // arrangement exactly (`Reminders.tsx`), which is the overlay's other list of rows with
    // buttons in them. The four buttons per row keep their own tab stops, and `Ctrl+↑` / `Ctrl+↓`
    // stay what they were: overlay-wide keys that cycle the chat without moving focus, which is
    // a listbox's job and no longer a promise this markup makes.
    <ul className="switcher" aria-label="Recent chats" ref={card}>
      {stack.entries.map(({ key, item: session, leaving }) => (
        // The `<li>` is outside the roll and the row inside it, the reminder stack's arrangement
        // and for the first of its two reasons: a list whose items are wrapper divs is not a list
        // to a screen reader. Its second reason, an adjacent-sibling hairline that a wrapper in
        // between switches off, does not apply here, the switcher drawing no rule between rows.
        // A third that stack did not have does: the row's `min-height` is what makes every shape
        // of it the same height, and left on the `<li>` it is also a floor the roll inside cannot
        // get under, so the row would animate to nothing inside a slot that never shrank.
        //
        // A leaving row is WITHDRAWN for the length of its exit. It is a chat that no longer
        // exists, and holding it on screen for 300ms otherwise leaves its four buttons live: the
        // roll would be 300ms in which the title still opens a deleted chat, the trash still asks
        // to delete it again, and the tab order still walks through all four.
        <li key={key} className="switcher-slot" {...withdrawn(leaving)}>
          <Collapse open={!leaving} onClosed={() => stack.released(key)}>
            <SessionRow
              session={session}
              shape={shapeOf(session.sessionId)}
              current={session.sessionId === currentId}
              now={now}
              draft={draft}
              onDraft={setDraft}
              onSelect={() => onSelect(session.sessionId)}
              onStartRename={() => startRename(session)}
              onCommitRename={() => endRename(session.sessionId, true)}
              onCancelRename={() => endRename(session.sessionId, false)}
              onStartDelete={() => startDelete(session.sessionId)}
              onConfirmDelete={() => confirmDelete(session.sessionId)}
              onCancelDelete={() => cancelDelete(session.sessionId)}
              onPin={() => onPin(session.sessionId, !session.pinned)}
            />
          </Collapse>
        </li>
      ))}
      {/* THE TWO DIRECTIONS OF THE EMPTY LINE ARE NOT ONE FLAG.
          It is asked of `sessions` and not of the rendered rows, so deleting the last chat puts it
          up in the same frame the row starts leaving, and `enter` grows it out of nothing over that
          row's own roll: the card eases from a row to a line instead of rolling to 14 and then
          snapping 39px back up to 53, which is what it did while this waited for the roll to end.
          Both are on screen together for those 300ms, which is why the line is BELOW the rows and
          not above them, and why it is the row's roll the panel rides along with (the first
          `data-morphing` in the tree, `panelPlacement`), the target it publishes being the one the
          card is actually going to.
          Going the other way it does not roll at all: it is unmounted in the frame a chat arrives.
          The line is not a row, it is what the list says when it has nothing to say, so it waits
          for the row it replaces and yields to the row that replaces it. Rolling it out instead was
          traced and is worse in exactly the way this is better: the arriving row's 50px lands at
          once and the line's 39 would then roll away underneath it, an overshoot bigger than the
          11px step that is left.
          Its words come from `overlay/notice.ts`, because the live region says the same thing when
          the last row leaves and a reader who hears one and then reads the other must not be told
          two different things about one empty list. */}
      {sessions.length === 0 && (
        <li className="switcher-empty-slot">
          <Collapse open enter={stack.entries.length > 0}>
            <div className="switcher-empty">{NO_OTHER_CHATS}</div>
          </Collapse>
        </li>
      )}
    </ul>
  );
}
