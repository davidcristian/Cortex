import { type RefObject, useRef, useState } from "react";

import type { SessionSummary } from "../bridge/types";
import { NO_OTHER_CHATS, RECENT_CHATS } from "../overlay/notice";
import { caretKey, heir, useRowCaret } from "../overlay/rowCaret";
import { useSectionCaret } from "../overlay/sectionCaret";
import { usePresence } from "../overlay/usePresence";
import { useTravel } from "../overlay/useTravel";
import { withdrawn } from "../overlay/withdrawn";
import { Collapse } from "./Collapse";
import { type RowShape, SessionRow } from "./SessionRow";

interface SessionListProps {
  readonly sessions: readonly SessionSummary[];
  readonly currentId: string;
  /** Whether the switcher is open. The list stays mounted for the length of its closing roll, so
   *  it observes the close with its own rows still on the page, and a close made while the caret
   *  was inside it moves the caret to the anchor below (`overlay/sectionCaret.ts`). */
  readonly open: boolean;
  /** `OverlayState.arrival`, for the same rule: most of the ways this list closes are chat swaps,
   *  and when a conversation is arriving the caret belongs to the composer (`Composer`). */
  readonly arrival: number;
  /** Where the caret goes when this list has no row left to receive it, which happens when the
   *  reader deletes the last chat other than the one they are in: the header control that opened
   *  the list. It is still on screen, it is what closes the list again, and it is the one control
   *  dedicated to this list (`overlay/rowCaret.ts`). The same control receives the caret when the
   *  list closes, so both cases this list cannot keep the caret through land in one place. */
  readonly anchor: RefObject<HTMLElement | null>;
  readonly onSelect: (sessionId: string) => void;
  /** Rename a chat (ADR-0021 management addendum): submit a new label, or an empty one to
   *  clear a custom title back to the derived one. A user-only write. */
  readonly onRename: (sessionId: string, title: string) => void;
  /** Delete a chat (ADR-0021 management addendum): a destructive, irreversible user-only write.
   *  Called only after this row's local "are you sure" confirm, so a stray click cannot delete. */
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
  open,
  arrival,
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
  // A deleted chat leaves `sessions` the moment the write lands, and the row goes on standing for
  // the length of its own roll (`usePresence`, shared with the reminder stack). Before this, the
  // row was gone in the frame the delete resolved and everything under it snapped up 50px into the
  // gap; the panel does not move at all, so that snap was the only thing visible. The hook holds no
  // clock: `Collapse` reports the roll over and the row is dropped then, which keeps the write
  // immediate and lets only the exit lag.
  const stack = usePresence(sessions, (session) => session.sessionId);
  // A row the list reorders animates to its new place. The brain lists pinned chats first and then
  // by recency, so pinning one regroups everything around it, and before this every row the
  // regrouping touched was at its new place in the frame the write landed (`overlay/useTravel.ts`
  // has the trace and the mechanism). Rows only: the empty line below is not a row and has no
  // second place to be in.
  const card = useRef<HTMLUListElement>(null);
  useTravel(card, ".switcher-slot");
  // The caret moves with the rows. Every gesture below removes the control that fired it from the
  // page, and each passes the caret on rather than dropping it on `<body>` (`overlay/rowCaret.ts`
  // carries the rule and the measurements). Placed after `useTravel`, so a row's new place is
  // settled before anything is focused inside it. Neither order changes the result today, since
  // focus moves nothing and `preventScroll` keeps it that way, and this order is the one that stays
  // correct if either of those changes.
  const caret = useRowCaret(card, anchor);
  // The list closing is the third way the caret can be left with nowhere to go. The rule above
  // covers the list reshaping under the reader; this one covers it being removed under them, which
  // `Ctrl+K` does from anywhere and the header's chats button does from the header
  // (`overlay/sectionCaret.ts` carries the rule, the guard and the measurements). Same anchor as
  // the emptied list above, and the same list element to ask about, so the caret is only moved for
  // a reader who had focus inside this list.
  useSectionCaret(card, anchor, open, arrival);

  const startRename = (session: SessionSummary): void => {
    setRenamingId(session.sessionId);
    setDraft(session.title);
    // The editor is a control the reader is expected to type into straight away, so it takes the
    // caret with the existing name selected.
    caret(caretKey("name", session.sessionId));
  };
  // Both ways out of an editor return the caret to the pencil that opened it, so the reader is left
  // on the row they were on and the pencil's own label reads the name they just gave it.
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
      // Deleting the chat on screen is a swap: a fresh chat arrives in its place and moves the
      // caret to the composer (`sessionState.deleteSession`, `Composer`). Claiming no caret here
      // lets that rule apply, rather than aiming the caret at a row and having the arriving chat
      // pull it out of the list a moment later.
      return;
    }
    // Every other delete leaves the reader in the list they are managing, on the row that has just
    // moved into the gap, and on the same control they pressed to make the gap, so deleting several
    // chats is one gesture repeated rather than a walk back into the list each time.
    caret(caretKey("delete", heir(sessions.map((session) => session.sessionId), sessionId)));
  };

  const shapeOf = (sessionId: string): RowShape => {
    if (sessionId === renamingId) {
      return "rename";
    }
    return sessionId === confirmingDeleteId ? "confirm" : "rest";
  };

  return (
    // A plain list of composite rows, which is what this is. It carried `role="listbox"` once,
    // which nothing under it satisfied: an option is a leaf and these rows are four buttons each,
    // so the container announced a listbox holding no options. Measured in Chromium, the missing
    // role was not the only cost. A `<li>` inside a listbox is not a listitem, so every row came
    // through as `none` and the boundaries a screen reader counts rows by were gone, leaving twelve
    // loose buttons in a list of nothing. Without the role the implicit list and listitem roles
    // come back and `aria-label` names the list, which is the arrangement the reminder stack uses
    // (`Reminders.tsx`), the overlay's other list of rows with buttons in them. The four buttons
    // per row keep their own tab stops, and `Ctrl+↑` / `Ctrl+↓` stay overlay-wide keys that cycle
    // the chat without moving focus, which is a listbox's behaviour and no longer something this
    // markup claims.
    <ul className="switcher" aria-label={RECENT_CHATS} ref={card}>
      {stack.entries.map(({ key, item: session, leaving }) => (
        // The `<li>` is outside the roll and the row inside it, which is the reminder stack's
        // arrangement, for the first of that stack's two reasons: a list whose items are wrapper
        // divs is not a list to a screen reader. Its second reason, an adjacent-sibling hairline
        // that a wrapper in between switches off, does not apply here, since the switcher draws no
        // rule between rows. A third reason applies here and not there: the row's `min-height` is
        // what makes every shape of it the same height, and on the `<li>` it would also be a floor
        // the roll inside cannot go under, so the row would animate to nothing inside a slot that
        // never shrank.
        //
        // A leaving row is withdrawn for the length of its exit, because it is a chat that no
        // longer exists. Left live for those 300ms, its title still opens a deleted chat, its trash
        // button still asks to delete it again, and the tab order still walks through all four
        // buttons.
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
      {/* The empty line appears and disappears by different rules.
          Its condition is read off `sessions` rather than off the rendered rows, so deleting the
          last chat mounts it in the same frame the row starts leaving, and `enter` grows it from
          nothing over that row's own roll: the card eases from a row to a line instead of rolling
          to 14 and then snapping 39px back up to 53, which is what it did while this waited for the
          roll to end. Both are on screen together for those 300ms, which is why the line is below
          the rows rather than above them, and why the panel follows the row's roll (the first
          `data-morphing` in the tree, `panelPlacement`), whose published target is the height the
          card is going to.
          On the way out the line does not roll: it is unmounted in the frame a chat arrives, so the
          arriving row takes its place immediately. Rolling it out was traced and is worse: the
          arriving row's 50px lands at once and the line's 39 would then roll away underneath it, an
          overshoot bigger than the 11px step that is left.
          Its words come from `overlay/notice.ts`, because the live region says the same thing when
          the last row leaves, and a reader who hears one and then reads the other must not be told
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
