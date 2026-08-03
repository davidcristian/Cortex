import { type ReactNode, useState } from "react";

import type { SessionSummary } from "../bridge/types";
import { usePresence } from "../overlay/usePresence";
import { withdrawn } from "../overlay/withdrawn";
import { Collapse } from "./Collapse";
import { CheckIcon, CloseIcon, PencilIcon, PinIcon, TrashIcon } from "./icons";
import { relativeTime } from "./relativeTime";

interface SessionListProps {
  readonly sessions: readonly SessionSummary[];
  readonly currentId: string;
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

  const startRename = (session: SessionSummary): void => {
    setRenamingId(session.sessionId);
    setDraft(session.title);
  };
  const commitRename = (sessionId: string): void => {
    onRename(sessionId, draft.trim());
    setRenamingId(null);
  };
  const confirmDelete = (sessionId: string): void => {
    onDelete(sessionId);
    setConfirmingDeleteId(null);
  };

  /** The three shapes one row can be in, all of them inside the roll and all of them the same
   *  height: `.switcher-row` carries the flex box and the resting row's height, so the one-line
   *  rename editor and the one-line confirm do not shorten the card as they open. */
  const rowFor = (session: SessionSummary): ReactNode => {
    if (session.sessionId === renamingId) {
      return (
        <div className="switcher-row">
          <form
            className="switcher-rename"
            onSubmit={(event) => {
              event.preventDefault();
              commitRename(session.sessionId);
            }}
          >
            <input
              className="switcher-rename-input"
              aria-label="New chat name"
              value={draft}
              onChange={(event) => setDraft(event.currentTarget.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setRenamingId(null);
                }
              }}
            />
            <button type="submit" className="switcher-rename-save" aria-label="Save name">
              <CheckIcon />
            </button>
          </form>
        </div>
      );
    }
    if (session.sessionId === confirmingDeleteId) {
      return (
        <div className="switcher-row">
          <div className="switcher-confirm-delete">
            <span className="switcher-confirm-text">Delete this chat?</span>
            <button
              type="button"
              className="switcher-confirm-yes"
              aria-label={`Confirm delete ${session.title}`}
              onClick={() => confirmDelete(session.sessionId)}
            >
              <TrashIcon />
            </button>
            <button
              type="button"
              className="switcher-confirm-no"
              aria-label="Cancel delete"
              onClick={() => setConfirmingDeleteId(null)}
            >
              <CloseIcon />
            </button>
          </div>
        </div>
      );
    }
    return (
      <div className={`switcher-row${session.pinned ? " pinned" : ""}`}>
        <button
          type="button"
          className={`switcher-item${session.sessionId === currentId ? " current" : ""}`}
          aria-current={session.sessionId === currentId}
          onClick={() => onSelect(session.sessionId)}
        >
          <span className="switcher-title">{session.title}</span>
          <span className="switcher-preview">{session.preview}</span>
        </button>
        <button
          type="button"
          className="switcher-delete-btn"
          aria-label={`Delete ${session.title}`}
          onClick={() => setConfirmingDeleteId(session.sessionId)}
        >
          <TrashIcon />
        </button>
        <button
          type="button"
          className="switcher-rename-btn"
          aria-label={`Rename ${session.title}`}
          onClick={() => startRename(session)}
        >
          <PencilIcon />
        </button>
        <button
          type="button"
          className={`switcher-pin-btn${session.pinned ? " on" : ""}`}
          aria-label={session.pinned ? `Unpin ${session.title}` : `Pin ${session.title}`}
          aria-pressed={session.pinned}
          onClick={() => onPin(session.sessionId, !session.pinned)}
        >
          <PinIcon filled={session.pinned} />
        </button>
        <span className="switcher-time">{relativeTime(session.lastActivityUnixMs, now)}</span>
      </div>
    );
  };

  return (
    <ul className="switcher" aria-label="Recent chats">
      {stack.entries.length === 0 ? (
        <li className="switcher-empty">No other chats yet</li>
      ) : (
        stack.entries.map(({ key, item: session, leaving }) => (
          <li key={key} className="switcher-slot" {...withdrawn(leaving)}>
            <Collapse open={!leaving} onClosed={() => stack.released(key)}>
              {rowFor(session)}
            </Collapse>
          </li>
        ))
      )}
    </ul>
  );
}
