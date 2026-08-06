import type { SessionSummary } from "../bridge/types";
import { caretKey } from "../overlay/rowCaret";
import { CheckIcon, CloseIcon, PencilIcon, PinIcon, TrashIcon } from "./icons";
import { relativeTime } from "./relativeTime";

/** Which of the three things a row is being right now. The list owns this, not the row: at most one
 *  row in the switcher is renaming and at most one is asking about a delete. */
export type RowShape = "rest" | "rename" | "confirm";

interface SessionRowProps {
  readonly session: SessionSummary;
  readonly shape: RowShape;
  /** Whether this row's chat is the one on the panel. */
  readonly current: boolean;
  /** The clock the row's relative time is read against, taken once per list render. */
  readonly now: number;
  /** The in-progress label while the shape is `rename`; the list holds it, so it survives this
   *  row re-rendering under a list refresh and dies with the editor rather than with the row. */
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

/**
 * One chat in the switcher, in whichever of its three shapes the list has it in.
 *
 * All three are the same height: `.switcher-row` carries the flex box and the resting row's
 * height, so the one-line rename editor and the one-line confirm do not shorten the card as they
 * open. Split out of `SessionList` when the caret rule below arrived, which is the list's business
 * to decide and the row's to be reachable for; the list is the rows plus their exits, and this is
 * what one of them looks like.
 *
 * WHAT THE `data-caret` NAMES ARE FOR. A gesture here takes the control that fired it off the page:
 * pressing the pencil unmounts the pencil, saving unmounts the editor, confirming a delete unmounts
 * the confirm. The list answers each one by naming the control the caret should land on next
 * (`overlay/rowCaret.ts`), and these attributes are how it says which. Four of the row's controls
 * are named and the fifth is not: the pin toggle survives its own gesture, measured holding focus
 * at every sample across the regroup it causes, so nothing has to be said about it.
 */
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
              if (event.key === "Escape") {
                // ESCAPE CLOSES THE INNERMOST THING, and this editor is the innermost thing there
                // is. The overlay listens for Escape on the window and dismisses the panel with it,
                // which is right when there is nothing smaller to close and wrong here: measured at
                // 900x900, cancelling a rename took the whole panel off the screen, so the gesture
                // that undoes a rename also ended the session. The console already gets this right
                // one layer up, closing itself instead of dismissing; it can do that from the
                // overlay's own handler because the overlay holds its state, and this editor's
                // lives in the row, so the row is what says the press was answered.
                event.stopPropagation();
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
          // The editor's rule, one shape over: Escape closes the innermost thing, and a question
          // standing over a row is innermost. Without it the press reached the window listener and
          // dismissed the whole panel with the question still open underneath, so the answer to
          // "delete this chat?" was waiting on the next summon. The caret is inside this box by the
          // time anyone can press it, which is what makes one handler on the box enough.
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
          {/* THE CARET LANDS HERE AND NOT ON THE TRASH BESIDE IT. The confirm exists so that one
              stray press cannot delete a chat, and the reader arrives at it having just pressed a
              key or a button to open it. Measured at 900x900: with focus on the confirm, one
              further Enter deletes the chat; with focus here, the same press puts the row back.
              Landing on the destructive half would make the second press of a key somebody is
              already holding down the whole of the decision, which is the class of accident the
              confirm was built for. */}
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
        // Which chat is already open was a background tint and nothing else, so the one row a
        // reader most needs to place sounded exactly like the others. `aria-current` is the
        // channel that says it, and `true` is its value for a current item that is none of the
        // enumerated kinds: a chat is not a page, a step, a location, a date or a time. Written
        // on every row rather than only the open one, the pin toggle's `aria-pressed` idiom, so
        // the state is a property of the row instead of an attribute that comes and goes.
        aria-current={current}
        onClick={onSelect}
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
