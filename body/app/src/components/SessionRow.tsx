import type { SessionSummary } from "../bridge/types";
import { fieldKey } from "../overlay/fieldKeys";
import { caretKey } from "../overlay/rowCaret";
import { CheckIcon, CloseIcon, PencilIcon, PinIcon, TrashIcon } from "./icons";
import { relativeTime } from "./relativeTime";

/** Which of its three shapes a row is in. The list holds this rather than the row, because at
 *  most one row in the switcher is renaming and at most one is asking about a delete. */
export type RowShape = "rest" | "rename" | "confirm";

interface SessionRowProps {
  readonly session: SessionSummary;
  readonly shape: RowShape;
  /** Whether this row's chat is the one on the panel. */
  readonly current: boolean;
  /** The clock the row's relative time is read against, taken once per list render. */
  readonly now: number;
  /** The in-progress label while the shape is `rename`. The list holds it, so it survives this
   *  row re-rendering under a list refresh. */
  readonly draft: string;
  readonly onDraft: (title: string) => void;
  readonly onSelect: () => void;
  readonly onStartRename: () => void;
  readonly onCommitRename: () => void;
  readonly onCancelRename: () => void;
  readonly onStartDelete: () => void;
  readonly onConfirmDelete: () => void;
  readonly onCancelDelete: () => void;
  readonly onPin: () => void;
}

/** One chat in the switcher, in whichever of its three shapes the list has it in. All three are
 *  the same height, so the rename editor and the confirm do not shorten the card. The `data-caret`
 *  attributes are how the list names the control the caret should go to next. */
export function SessionRow({
  session,
  shape,
  current,
  now,
  draft,
  onDraft,
  onSelect,
  onStartRename,
  onCommitRename,
  onCancelRename,
  onStartDelete,
  onConfirmDelete,
  onCancelDelete,
  onPin,
}: SessionRowProps) {
  const id = session.sessionId;
  if (shape === "rename") {
    return (
      <div className="switcher-row">
        <form
          className="switcher-rename"
          onSubmit={(event) => {
            event.preventDefault();
            onCommitRename();
          }}
        >
          <input
            className="switcher-rename-input"
            data-caret={caretKey("name", id)}
            aria-label="New chat name"
            value={draft}
            onChange={(event) => onDraft(event.currentTarget.value)}
            onKeyDown={(event) => {
              // Two keys stop here. Escape closes the innermost open thing, which here is the
              // editor, and the overlay's own handler would dismiss the panel instead. A chord
              // waits until the name is settled, because the label dies with the editor.
              const answer = fieldKey(event);
              if (answer === "pass") {
                return;
              }
              event.stopPropagation();
              if (answer === "cancel") {
                onCancelRename();
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
  if (shape === "confirm") {
    return (
      <div className="switcher-row">
        <div
          className="switcher-confirm-delete"
          // The same Escape rule as the rename editor: an open question over a row is the
          // innermost open thing. A chord passes straight through, because a confirm holds no
          // text to lose.
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.stopPropagation();
              onCancelDelete();
            }
          }}
        >
          <span className="switcher-confirm-text">Delete this chat?</span>
          <button
            type="button"
            className="switcher-confirm-yes"
            aria-label={`Confirm delete ${session.title}`}
            onClick={onConfirmDelete}
          >
            <TrashIcon />
          </button>
          {/* The caret goes to cancel rather than to the confirm beside it: the reader has just
              pressed a key or a button to get here, and one more Enter on the confirm would delete
              the chat, which is the accident the confirm exists to prevent. */}
          <button
            type="button"
            className="switcher-confirm-no"
            data-caret={caretKey("keep", id)}
            aria-label="Cancel delete"
            onClick={onCancelDelete}
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
        className={`switcher-item${current ? " current" : ""}`}
        // `true` rather than one of the enumerated kinds, because a chat is not a page, a step, a
        // location, a date or a time. Written on every row, so the state is a property of the row
        // instead of an attribute that appears and disappears.
        aria-current={current}
        onClick={onSelect}
      >
        <span className="switcher-title">{session.title}</span>
        <span className="switcher-preview">{session.preview}</span>
      </button>
      {/* Right to left: the time, then the `pin`, the pencil and the trash. The time takes the
          edge because it is what a reader skimming for a chat looks at, and the three controls
          stand inboard of it in the order they escalate. */}
      <button
        type="button"
        className="switcher-delete-btn"
        data-caret={caretKey("delete", id)}
        aria-label={`Delete ${session.title}`}
        onClick={onStartDelete}
      >
        <TrashIcon />
      </button>
      <button
        type="button"
        className="switcher-rename-btn"
        data-caret={caretKey("rename", id)}
        aria-label={`Rename ${session.title}`}
        onClick={onStartRename}
      >
        <PencilIcon />
      </button>
      <button
        type="button"
        className={`switcher-pin-btn${session.pinned ? " on" : ""}`}
        aria-label={session.pinned ? `Unpin ${session.title}` : `Pin ${session.title}`}
        aria-pressed={session.pinned}
        onClick={onPin}
      >
        <PinIcon filled={session.pinned} />
      </button>
      <span className="switcher-time">{relativeTime(session.lastActivityUnixMs, now)}</span>
    </div>
  );
}
