import { useState } from "react";

import type { SessionSummary } from "../bridge/types";
import { CheckIcon, CloseIcon, PencilIcon, TrashIcon } from "./icons";
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
}

/** The switcher dropdown: recent chats with title, relative time, and a one-line preview, each
 *  with inline rename and delete affordances. Store-backed (ADR-0021); selecting one loads its
 *  history, renaming writes its display title, and deleting removes it (behind a per-row confirm,
 *  since it is destructive and irreversible), the overlay re-listing to reflect either write. */
export function SessionList({ sessions, currentId, onSelect, onRename, onDelete }: SessionListProps) {
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
            <li key={session.sessionId} className="switcher-li">
              <button
                type="button"
                className={`switcher-item${session.sessionId === currentId ? " current" : ""}`}
                onClick={() => onSelect(session.sessionId)}
              >
                <span className="switcher-row">
                  <span className="switcher-title">{session.title}</span>
                  <span className="switcher-time">
                    {relativeTime(session.lastActivityUnixMs, now)}
                  </span>
                </span>
                <span className="switcher-preview">{session.preview}</span>
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
                className="switcher-delete-btn"
                aria-label={`Delete ${session.title}`}
                onClick={() => setConfirmingDeleteId(session.sessionId)}
              >
                <TrashIcon />
              </button>
            </li>
          );
        })
      )}
    </ul>
  );
}
