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
  /** Whether the switcher is open. The list is mounted for the length of its closing roll, so it
   *  hears the close with its own rows still on the page, and a close the reader made under the
   *  caret hands the caret to the anchor below (`overlay/sectionCaret.ts`). */
  readonly open: boolean;
  /** `OverlayState.arrival`, for the same rule: most of the ways this list closes are chat swaps,
   *  and a caret that a conversation is arriving for belongs to the composer (`Composer`). */
  readonly arrival: number;
  /**
   * Where the caret goes when this list has no row left to hand it to, which is the chat the
   * reader just deleted their last other one from: the header control that opened the list.
   */
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

/**
 * The switcher dropdown: recent chats with title, relative time, and a one-line preview, each with
 * inline pin, rename, and delete affordances.
 */
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
  const stack = usePresence(sessions, (session) => session.sessionId);
  const card = useRef<HTMLUListElement>(null);
  useTravel(card, ".switcher-slot");
  const caret = useRowCaret(card, anchor);
  useSectionCaret(card, anchor, open, arrival);

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
    <ul className="switcher" aria-label={RECENT_CHATS} ref={card}>
      {stack.entries.map(({ key, item: session, leaving }) => (
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
