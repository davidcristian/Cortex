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
  // A deleted chat leaves `sessions` the moment the write lands, and the row it takes with it
  // stays on screen for the length of its own roll (`usePresence`, shared with the reminder
  // stack). Before this, the row was gone in the frame the delete resolved and everything under it
  // snapped up 50px into the hole; the panel does not move at all, so that snap was the whole of
  // what the eye saw. The hook holds no clock: `Collapse` reports the roll over and the row is
  // dropped then, which is what keeps the WRITE immediate and only the exit lagging.
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
          // Which chat is already open was a background tint and nothing else, so the one row a
          // reader most needs to place sounded exactly like the others. `aria-current` is the
          // channel that says it, and `true` is its value for a current item that is none of the
          // enumerated kinds: a chat is not a page, a step, a location, a date or a time. Written
          // on every row rather than only the open one, the pin toggle's `aria-pressed` idiom, so
          // the state is a property of the row instead of an attribute that comes and goes.
          aria-current={session.sessionId === currentId}
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
        <span className="switcher-time">{relativeTime(session.lastActivityUnixMs, now)}</span>
      </div>
    );
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
    <ul className="switcher" aria-label="Recent chats">
      {/* Asked of the RENDERED rows and not of `sessions`, so deleting the last chat does not put
          the empty line up while the row it replaces is still rolling out underneath it. The line
          itself still arrives in one frame, once the roll has ended and there is nothing left to
          collide with; rolling it in as well was traced and is worse, because the opposite case (a
          first chat arriving into an empty list) would then grow the list by the new row and only
          then roll the line away, overshooting by the row's own height. */}
      {stack.entries.length === 0 ? (
        <li className="switcher-empty">No other chats yet</li>
      ) : (
        stack.entries.map(({ key, item: session, leaving }) => (
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
              {rowFor(session)}
            </Collapse>
          </li>
        ))
      )}
    </ul>
  );
}
