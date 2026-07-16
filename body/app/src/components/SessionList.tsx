import { useState } from "react";

import type { SessionSummary } from "../bridge/types";
import { CheckIcon, PencilIcon } from "./icons";
import { relativeTime } from "./relativeTime";

interface SessionListProps {
  readonly sessions: readonly SessionSummary[];
  readonly currentId: string;
  readonly onSelect: (sessionId: string) => void;
  /** Rename a chat (ADR-0021 management addendum): submit a new label, or an empty one to
   *  clear a custom title back to the derived one. A user-only write. */
  readonly onRename: (sessionId: string, title: string) => void;
}

/** The switcher dropdown: recent chats with title, relative time, and a one-line preview,
 *  each with an inline rename affordance. Store-backed (ADR-0021); selecting one loads its
 *  history, renaming one writes its display title and the overlay re-lists to show it. */
export function SessionList({ sessions, currentId, onSelect, onRename }: SessionListProps) {
  const now = Date.now();
  // Which row is being renamed (at most one), and its in-progress label. Local UI state only:
  // the committed title lives in the store, and the switcher re-lists to reflect it.
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const startRename = (session: SessionSummary): void => {
    setRenamingId(session.sessionId);
    setDraft(session.title);
  };
  const commitRename = (sessionId: string): void => {
    onRename(sessionId, draft.trim());
    setRenamingId(null);
  };

  return (
    <ul className="switcher" role="listbox" aria-label="Recent chats">
      {sessions.length === 0 ? (
        <li className="switcher-empty">No other chats yet</li>
      ) : (
        sessions.map((session) =>
          session.sessionId === renamingId ? (
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
          ) : (
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
            </li>
          ),
        )
      )}
    </ul>
  );
}
