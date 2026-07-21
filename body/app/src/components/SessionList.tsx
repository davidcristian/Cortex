import { useState } from "react";

import type { SessionSummary } from "../bridge/types";
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

/** The switcher dropdown: recent chats with title, relative time, and a one-line preview, each
 *  with inline pin, rename, and delete affordances. Store-backed (ADR-0021); selecting one loads
 *  its history, pinning lifts it above the recency window, renaming writes its display title, and
 *  deleting removes it (behind a per-row confirm), the overlay re-listing to reflect each write.
 *  The brain returns pinned chats first (ADR-0021 pinning addendum), so the pinned group renders at
 *  the top; each pinned row carries a filled pin indicator, making the grouping legible. */
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

  return (
    <ul className="switcher" role="listbox" aria-label="Recent chats">
      {sessions.length === 0 ? (
        <li className="switcher-empty">No other chats yet</li>
      ) : (
        sessions.map((session) => {
          if (session.sessionId === renamingId) {
            return (
              <li key={session.sessionId} className="switcher-li">
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
              </li>
            );
          }
          if (session.sessionId === confirmingDeleteId) {
            return (
              <li key={session.sessionId} className="switcher-li">
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
              </li>
            );
          }
          return (
            <li key={session.sessionId} className={`switcher-li${session.pinned ? " pinned" : ""}`}>
              <button
                type="button"
                className={`switcher-item${session.sessionId === currentId ? " current" : ""}`}
                onClick={() => onSelect(session.sessionId)}
              >
                <span className="switcher-title">{session.title}</span>
                <span className="switcher-preview">{session.preview}</span>
              </button>
              {/* Right to left: the time, then the pin, the pencil and the trash. The time is the
                  one the eye goes to when it is skimming for a chat, so it takes the edge and the
                  three controls sit inboard of it, in the order they escalate. It is outside the
                  row's button because it is now on the far side of three buttons that are not, and
                  a label is not a thing to click anyway; what selects the chat is the title, the
                  preview and the space between them. */}
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
              <span className="switcher-time">
                {relativeTime(session.lastActivityUnixMs, now)}
              </span>
            </li>
          );
        })
      )}
    </ul>
  );
}
