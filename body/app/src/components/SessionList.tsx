import type { SessionSummary } from "../bridge/types";
import { relativeTime } from "./relativeTime";

interface SessionListProps {
  readonly sessions: readonly SessionSummary[];
  readonly currentId: string;
  readonly onSelect: (sessionId: string) => void;
}

/** The switcher dropdown: recent chats with title, relative time, and a one-line preview.
 *  Store-backed (ADR-0021); selecting one loads its history. */
export function SessionList({ sessions, currentId, onSelect }: SessionListProps) {
  const now = Date.now();
  return (
    <ul className="switcher" role="listbox" aria-label="Recent chats">
      {sessions.length === 0 ? (
        <li className="switcher-empty">No other chats yet</li>
      ) : (
        sessions.map((session) => (
          <li key={session.sessionId}>
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
          </li>
        ))
      )}
    </ul>
  );
}
