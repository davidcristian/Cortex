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
   *  it sees the close with its own rows still on the page. */
  readonly open: boolean;
  /** `OverlayState.arrival`, for the same rule: most of the ways this list closes are chat swaps,
   *  and when a conversation is arriving the caret belongs to the composer (`Composer`). */
  readonly arrival: number;
  /** Where the caret goes when this list has no row left to receive it, which happens when the
   *  reader deletes the last chat other than the one they are in: the header control that opened
   *  the list. The same control receives the caret when the list closes. */
  readonly anchor: RefObject<HTMLElement | null>;
  readonly onSelect: (sessionId: string) => void;
  /** Rename a chat: submit a new label, or an empty one to clear a custom title back to the one
   *  the brain derives. */
  readonly onRename: (sessionId: string, title: string) => void;
  /** Delete a chat. Irreversible, and called only after this row's own confirm, so a stray click
   *  cannot delete. */
  readonly onDelete: (sessionId: string) => void;
  /** Set whether the brain lists this chat however old it is. Takes effect at once, with no
   *  confirm. */
  readonly onPin: (sessionId: string, pinned: boolean) => void;
}

/** The switcher dropdown: recent chats with title, relative time, and a one-line preview, each
 *  with its own `pin`, rename and delete controls. The brain returns the `pinned` chats first, so
 *  that group renders at the top. */
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
  // Local state only, in the list rather than the row: at most one row is renaming and at most
  // one is asking about a delete. The committed title lives in the store.
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  // A deleted chat leaves `sessions` as soon as the write resolves, and the row stays on screen
  // for the length of its own roll. Without this the row was gone in that frame and everything
  // under it snapped up 50px into the gap, which was the only visible movement.
  const stack = usePresence(sessions, (session) => session.sessionId);
  // A row the list reorders animates to its new place, which matters because the brain lists the
  // `pinned` chats first and then by recency, so one such write regroups everything around it.
  // Rows only: the empty line below is not a row and has no second place to be in.
  const card = useRef<HTMLUListElement>(null);
  useTravel(card, ".switcher-slot");
  // Every gesture below removes the control that fired it, and each passes the caret on rather
  // than dropping it on `<body>`. After `useTravel`, so a row's new place is settled before
  // anything inside it is focused.
  const caret = useRowCaret(card, anchor);
  // The list closing is the other way the caret can be left with nowhere to go, which `Ctrl+K`
  // does from anywhere and the header's chats button does from the header.
  useSectionCaret(card, anchor, open, arrival);

  const startRename = (session: SessionSummary): void => {
    setRenamingId(session.sessionId);
    setDraft(session.title);
    caret(caretKey("name", session.sessionId));
  };
  // Both ways out of an editor return the caret to the pencil that opened it.
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
      // Deleting the chat on screen is a swap: a fresh chat arrives in its place and takes the
      // caret to the composer. Claiming no caret here lets that happen.
      return;
    }
    // Every other delete leaves the reader on the row that has just moved into the gap, and on the
    // same control they pressed, so deleting several chats is one gesture repeated.
    caret(caretKey("delete", heir(sessions.map((session) => session.sessionId), sessionId)));
  };

  const shapeOf = (sessionId: string): RowShape => {
    if (sessionId === renamingId) {
      return "rename";
    }
    return sessionId === confirmingDeleteId ? "confirm" : "rest";
  };

  return (
    // A plain list, not `role="listbox"`: an option is a leaf and these rows are four buttons
    // each, and inside a listbox a `<li>` is not a listitem, so the row boundaries a screen reader
    // counts disappeared and twelve loose buttons were left in a list of nothing.
    <ul className="switcher" aria-label={RECENT_CHATS} ref={card}>
      {stack.entries.map(({ key, item: session, leaving }) => (
        // The `<li>` is outside the roll and the row inside it, because a list whose items are
        // wrapper divs is not a list to a screen reader, and the row's `min-height` on the `<li>`
        // would stop the roll shrinking. A leaving row is withdrawn: the chat no longer exists.
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
      {/* Mounted off `sessions` rather than off the rendered rows, so deleting the last chat
          grows this line over that row's own roll, and unmounted at once when a chat arrives,
          because rolling it away under the arriving row overshoots. Its words are the notice's. */}
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
