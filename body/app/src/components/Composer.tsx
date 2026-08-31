import {
  type KeyboardEvent,
  type MutableRefObject,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { SendIcon, StopIcon } from "./icons";

interface ComposerProps {
  /** The field itself, held by the view above so that the panel's other surfaces can hand the caret
   *  back to the conversation. */
  readonly field: MutableRefObject<HTMLTextAreaElement>;
  readonly busy: boolean;
  /** What this conversation is holding, unsent. The field is controlled by this rather than
   *  keeping its own copy, so a chat swap hands it that chat's text in the same commit. */
  readonly draft: string;
  /** Every keystroke, parked under the chat on screen. */
  readonly onDraft: (text: string) => void;
  /** Which conversation this field belongs to, or null while the panel is shut or the console is
   *  over the chat. The field takes focus on every change. */
  readonly arrival: number | null;
  readonly onSubmit: (text: string) => void;
  readonly onStop: () => void;
  /** Called when the pill's own height changes, before the frame that shows it. Must be stable:
   *  it is a dependency of the measurement below. */
  readonly onResize: () => void;
}

/** The tallest the field grows to, matching its CSS max-height. */
const FIELD_MAX_PX = 120;

/** The class that turns the pill into two rows: the field across it, the button on its own row
 *  beneath. */
const STACKED = "stacked";

/** The prompt input: Enter sends, Shift+Enter newlines, and the field grows with its content up to
 *  a few lines. */
export function Composer({
  field: fieldRef,
  busy,
  draft,
  arrival,
  onSubmit,
  onDraft,
  onStop,
  onResize,
}: ComposerProps) {
  const [stacked, setStacked] = useState(false);
  const pillRef = useRef<HTMLDivElement>(null!);
  // The pill's last measured height, so a resize is reported and a keystroke is not. It starts at
  // 0, so the first measurement always reports.
  const pillHeight = useRef(0);

  useEffect(() => {
    if (arrival !== null) {
      // Without `preventScroll` the engine scrolls the panel to bring the field into view, and
      // the whole panel's contents slide with it while the panel is still easing to its height.
      fieldRef.current.focus({ preventScroll: true });
    }
  }, [arrival]);

  const measure = useCallback(() => {
    const field = fieldRef.current;
    const pill = pillRef.current;
    // The layout is always chosen at the inline width: a stacked field is 44px wider, so deciding
    // at the width in use would unstack a draft that just wrapped and then stack it again. The
    // pill's height is held meanwhile, or the log beside it grows and Chromium clamps its scroll.
    pill.style.minHeight = `${pill.offsetHeight}px`;
    pill.classList.remove(STACKED);
    field.style.height = "auto";
    // A `rows={1}` textarea's auto height is one row, so this compares against the measured
    // one-line height and a wrapped long line counts exactly like a typed newline.
    const wraps = field.scrollHeight > field.clientHeight;
    // Applied before the height is read, because a stacked field is wider and may need fewer lines
    // than the decision above did.
    pill.classList.toggle(STACKED, wraps);
    setStacked(wraps);
    field.style.height = `${Math.min(field.scrollHeight, FIELD_MAX_PX)}px`;
    pill.style.minHeight = "";
    const height = pill.offsetHeight;
    if (height !== pillHeight.current) {
      pillHeight.current = height;
      onResize();
    }
  }, [onResize]);

  // A layout effect, not a paint-time one: the measurement both chooses a layout and sizes the
  // field, so it has to run before the frame that shows the new character.
  useLayoutEffect(measure, [draft, measure]);

  // The width changes the answer too, and the width can move while the draft stands still. Only
  // the draft re-runs the measurement, so without this both readings stay at the old width.
  useEffect(() => {
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure]);

  // The state that holds the draft empties the field, not this component, so a send that the turn
  // state rejects leaves the text where it is.
  const submit = () => {
    if (busy) {
      return;
    }
    onSubmit(draft);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const live = draft.trim().length > 0 && !busy;

  return (
    <div ref={pillRef} className={`composer${stacked ? ` ${STACKED}` : ""}`}>
      {/* The caret ends up at the end of a restored draft: assigning a textarea's value puts the
          selection there, and a chat swap is the only thing that changes the value React writes.
          A keystroke's value already matches, so a caret typing mid-sentence stays put. */}
      <textarea
        ref={fieldRef}
        className="field"
        value={draft}
        onChange={(event) => onDraft(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask anything…"
        aria-label="Message"
        rows={1}
      />
      <button
        className={`send${live ? " live" : ""}${busy ? " stopping" : ""}`}
        onClick={busy ? onStop : submit}
        aria-label={busy ? "Stop" : "Send"}
        type="button"
      >
        <span className="send-glyph">{busy ? <StopIcon /> : <SendIcon />}</span>
      </button>
    </div>
  );
}
