import type { SessionSummary } from "../bridge/types";
import { fieldKey } from "../overlay/fieldKeys";
import { caretKey } from "../overlay/rowCaret";
import { CheckIcon, CloseIcon, PencilIcon, PinIcon, TrashIcon } from "./icons";
import { relativeTime } from "./relativeTime";

/** Which of its three shapes a row is in. The list holds this rather than the row, because at most
 *  one row in the switcher is renaming and at most one is asking about a delete. */
export type RowShape = "rest" | "rename" | "confirm";

interface SessionRowProps {
  readonly session: SessionSummary;
  readonly shape: RowShape;
  /** Whether this row's chat is the one on the panel. */
  readonly current: boolean;
  /** The clock the row's relative time is read against, taken once per list render. */
  readonly now: number;
  /** The in-progress label while the shape is `rename`. The list holds it, so it survives this row
   *  re-rendering under a list refresh and is discarded with the editor rather than with the row. */
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
 * open. Split out of `SessionList` when the caret rule below arrived, since the list decides where
 * the caret goes and the row only has to be addressable.
 *
 * The `data-caret` attributes are how the list addresses a control. A gesture here removes the
 * control that fired it: pressing the pencil unmounts the pencil, saving unmounts the editor,
 * confirming a delete unmounts the confirm. The list names the control the caret should land on
 * next (`overlay/rowCaret.ts`), and it names it by these attributes. Four of the row's controls
 * are named and the fifth is not, because the pin toggle survives its own gesture: it was measured
 * holding focus at every sample across the regroup it causes.
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
              // Which keys this editor stops before they reach the window (`overlay/fieldKeys.ts`
              // holds the rule and the traces behind it). Two of them.
              //
              // Escape closes the innermost open thing, and inside this editor that is the editor.
              // The overlay listens for Escape on the window and dismisses the panel with it, which
              // is right when there is nothing smaller to close and wrong here: measured at
              // 900x900, cancelling a rename took the whole panel off the screen, so the gesture
              // that undoes a rename ended the session.
              //
              // A chord waits until the name is settled, because the in-progress label lives in the
              // list's state, dies with the editor, and has no undo behind it: measured the same
              // way, Ctrl+N over a typed name minted a chat, closed the switcher and left the row
              // reading its old title. The console handles Escape one layer up, from the overlay's
              // own handler, because the overlay holds the console's state; this editor's state
              // lives in the row, so the row is what reports that a press was handled.
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
          // The same Escape rule as the rename editor: an open question over a row is the innermost
          // open thing. Without this the press reached the window listener and dismissed the whole
          // panel with the question still open underneath, so "delete this chat?" was waiting on the
          // next summon. The caret is inside this box by the time anyone can press Escape, which is
          // what makes one handler on the box enough.
          //
          // The editor's other rule deliberately stops here: a chord passes straight through this
          // box. That rule protects text a surface would discard, and a confirm holds none, so
          // Ctrl+N over an open question costs one press to ask it again. Measured at 900x900: the
          // chat was minted, the switcher closed, the caret went to the composer, and nothing was
          // deleted.
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
          {/* The caret lands on cancel rather than on the confirm beside it. The confirm exists so
              that one stray press cannot delete a chat, and the reader arrives at it having just
              pressed a key or a button to open it. Measured at 900x900: with focus on the confirm,
              one further Enter deletes the chat; with focus here, the same press puts the row back.
              Landing on the destructive control would let a repeated keypress make the whole
              decision, which is the accident the confirm was added to prevent. */}
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
        // Which chat is already open used to be a background tint and nothing else, so the one row
        // a reader most needs to locate sounded exactly like the others. `aria-current` carries it,
        // and `true` is its value for a current item that is none of the enumerated kinds: a chat
        // is not a page, a step, a location, a date or a time. Written on every row rather than
        // only the open one, following the pin toggle's `aria-pressed`, so the state is a property
        // of the row instead of an attribute that appears and disappears.
        aria-current={current}
        onClick={onSelect}
      >
        <span className="switcher-title">{session.title}</span>
        <span className="switcher-preview">{session.preview}</span>
      </button>
      {/* Right to left: the time, then the pin, the pencil and the trash. The time is what a reader
          skimming for a chat looks at, so it takes the edge and the three controls sit inboard of
          it, in the order they escalate. It sits outside the row's button because it is on the far
          side of three buttons that are also outside it, and because a timestamp is not a control;
          what selects the chat is the title, the preview and the space between them. */}
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
