import { type KeyboardEvent, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { SendIcon, StopIcon } from "./icons";

interface ComposerProps {
  readonly busy: boolean;
  /** What this conversation is holding, unsent. */
  readonly draft: string;
  /** Every keystroke, parked under the chat on screen. Called with the field's raw value. */
  readonly onDraft: (text: string) => void;
  /**
   * Which conversation this field is sitting in (`OverlayState.arrival`), or null while the panel
   * is shut or the console is over the chat.
   */
  readonly arrival: number | null;
  readonly onSubmit: (text: string) => void;
  readonly onStop: () => void;
  /** Called when the pill's own height changes, before the frame that shows it. The pill is a flex
   *  sibling of the scrolling log, so its growth is the log's loss and the container has to react
   *  to it. Must be stable, since it is a dependency of the measurement below. */
  readonly onResize: () => void;
}

/** The auto-grow ceiling, matching the field's CSS max-height (a few lines, §3). */
const FIELD_MAX_PX = 120;

/** The class that turns the pill into two rows: the field across it, the button on its own row
 *  beneath. The layout itself is entirely CSS (`.composer.stacked` in overlay.css). */
const STACKED = "stacked";

/**
 * The prompt input: Enter sends, Shift+Enter newlines, and the field grows with its content up to
 * a few lines.
 */
export function Composer({
  busy,
  draft,
  arrival,
  onSubmit,
  onDraft,
  onStop,
  onResize,
}: ComposerProps) {
  const [stacked, setStacked] = useState(false);
  // Both are always mounted with the panel, so the refs are set before any effect runs.
  const fieldRef = useRef<HTMLTextAreaElement>(null!);
  const pillRef = useRef<HTMLDivElement>(null!);
  // The pill's last measured height, so the container hears about a resize and not about a
  // keystroke. Starts at 0, which the first measurement is free to disagree with.
  const pillHeight = useRef(0);

  useEffect(() => {
    if (arrival !== null) {
      fieldRef.current.focus({ preventScroll: true });
    }
  }, [arrival]);

  // Both questions below are asked of the text AND of the width it is laid out at, so this is a
  // function rather than an effect body: a keystroke is not the only thing that can change the
  // answer. `useCallback` because it is the dependency of the two effects that call it.
  const measure = useCallback(() => {
    const field = fieldRef.current;
    const pill = pillRef.current;
    pill.style.minHeight = `${pill.offsetHeight}px`;
    pill.classList.remove(STACKED);
    // Auto-grow starts here too: the field is collapsed once, and stays collapsed until the last
    // line, so both readings below are of the content rather than of the box's last size.
    field.style.height = "auto";
    // A `rows={1}` textarea's auto height IS one row, so its client height is the one-line height,
    // measured rather than assumed: no font metric, line height or padding is restated here, and a
    // wrapped long line counts exactly like a typed newline because both overflow one row.
    const wraps = field.scrollHeight > field.clientHeight;
    // Applied before the height is taken, because the height belongs to the layout that will be on
    // screen: a stacked field is wider and may need fewer lines than the decision above did.
    // React's own render (from `setStacked`) writes the same class back, so nothing flickers.
    pill.classList.toggle(STACKED, wraps);
    setStacked(wraps);
    // Now follow the content's scroll height up to the ceiling; past it the field scrolls
    // internally (the CSS max-height is the same bound).
    field.style.height = `${Math.min(field.scrollHeight, FIELD_MAX_PX)}px`;
    pill.style.minHeight = "";
    const height = pill.offsetHeight;
    if (height !== pillHeight.current) {
      pillHeight.current = height;
      onResize();
    }
  }, [onResize]);

  useLayoutEffect(measure, [draft, measure]);

  useEffect(() => {
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure]);

  // The field is emptied by the state that holds it, not from here: a turn actually starting is what
  // spends a draft, so a send the controller refuses (a blank field, a turn already streaming) leaves
  // the text where it is instead of quietly eating it (`overlay/turnState.ts`).
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
