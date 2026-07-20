import { type KeyboardEvent, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { SendIcon, StopIcon } from "./icons";

interface ComposerProps {
  readonly busy: boolean;
  /** True while the panel is open AND the chat is the view it is showing; the field takes focus on
   *  the rising edge, which is a summon and also a return from the console. */
  readonly active: boolean;
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

/** The prompt input: Enter sends, Shift+Enter newlines, and the field grows with its content
 *  up to a few lines. Focus lands here whenever the panel opens (design/overlay-ux.md §7).
 *  While a turn streams the send button becomes a stop that cancels it (§3).
 *
 *  Past one line the pill restacks: on a single line the button is a flex sibling of the field,
 *  which is fine, but it reserves its column down the WHOLE pill, so every wrapped line stopped
 *  44px short of the right edge for no visible reason and the button floated alone at the bottom
 *  of a tall empty column. Stacked, the text uses the full width and the button sits under it,
 *  right aligned, where the eye already looks for it. Both layouts leave the button in the same
 *  corner of the same content box, one as the last item of a bottom-aligned row and one as the
 *  last row of a column, so the switch never moves it: traced character by character over two
 *  lines, its rect was identical in all 183 samples. */
export function Composer({ busy, active, onSubmit, onStop, onResize }: ComposerProps) {
  const [text, setText] = useState("");
  const [stacked, setStacked] = useState(false);
  // Both are always mounted with the panel, so the refs are set before any effect runs.
  const fieldRef = useRef<HTMLTextAreaElement>(null!);
  const pillRef = useRef<HTMLDivElement>(null!);
  // The pill's last measured height, so the container hears about a resize and not about a
  // keystroke. Starts at 0, which the first measurement is free to disagree with.
  const pillHeight = useRef(0);

  useEffect(() => {
    if (active) {
      // WITHOUT SCROLLING ANYTHING. The panel clips its overflow, which makes it a scroll container
      // the user can never scroll but the ENGINE can, and bringing a newly focused element into
      // view is exactly when it does. Coming back from the console the panel is still the console's
      // height and easing to the chat's, and this field is below its clipped edge for the length of
      // that ease, so the engine scrolled the panel to reach it and every row in the window lurched
      // up with it. Traced at 60Hz at 640x720 with the session list open: `panel.scrollTop` went 0
      // to 139 in the frame focus landed and unwound over the ease, which is the whole panel's
      // contents sliding 139px and creeping back. The field is where the eye already is; it does
      // not need bringing into view, it needs the caret.
      fieldRef.current.focus({ preventScroll: true });
    }
  }, [active]);

  // Both questions below are asked of the text AND of the width it is laid out at, so this is a
  // function rather than an effect body: a keystroke is not the only thing that can change the
  // answer. `useCallback` because it is the dependency of the two effects that call it.
  const measure = useCallback(() => {
    const field = fieldRef.current;
    const pill = pillRef.current;
    // WHICH layout to use is always decided at the INLINE width, whatever layout is on screen.
    // Deciding it at the width in use feeds the two layouts to each other: a stacked field is 44px
    // wider (the button's column, given back), so a draft that just wrapped fits on one line again
    // the moment the button leaves its side, which would unstack it, re-wrap it, and stack it
    // again. That band is real, not theoretical: traced in Chromium at the panel's 560px, a line of
    // prose needs two lines inline and one stacked for five or six characters, and where the band
    // starts depends on the glyphs (60 through 65 on one traced line, 62 through 66 on another).
    // Measuring at one fixed width makes the choice a function of the text alone, so it
    // cannot chase itself; the band's cost is a pill one row roomier than its text needs, where
    // deciding at the stacked width instead would put the reserved column's defect back into it.
    //
    // HOLD THE PILL'S FLOOR FOR THE LENGTH OF THE MEASUREMENT. Everything below is a real relayout
    // of the whole panel, and an unpainted relayout costs nothing right up to the moment one of
    // them touches state that outlives it. This one does. Once the panel is at its ceiling the
    // column is in deficit and every child gives up what it can, and the only reason the pill keeps
    // its height is the floor under it: stacked, it cannot go below one row of field plus the
    // button's row (`.composer.stacked`'s `min-height`, which stands in for the automatic minimum
    // it replaces). Dropping the class drops that floor to a single row, so mid-measurement the
    // pill collapses and the scrolling log, the sibling that yields, grows into the gap.
    // Chromium then clamps the log's `scrollTop` to the shorter content it suddenly has room for.
    // The pill comes back; the clamp does not. Traced from inside the measurement at 640x720 with a
    // two-turn chat: the pill read 100px on entry, 75px with the class off, 100px on exit, and the log
    // 144, 169, 144 around it, its `scrollTop` left at 62 where the tail was 87. So every keystroke
    // AFTER the one that grew the pill quietly walked the newest reply back off the bottom edge.
    // `min-height` and not `height`, because the automatic minimum is precisely the thing that
    // moves. It cannot change the answer either: the question below is about the field's WIDTH.
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
    // The measurement is over, so the pill goes back to sizing itself and the only relayout that
    // outlives it is the intended one. Then say so, while the writes are still unpainted.
    // The pill is measured rather than predicted from the two numbers just written, because it is
    // the pill's height the container cares about and the engine is the authority on it. Only a
    // real change is reported: typing inside one line must not reach out of this component at all,
    // and a stream re-rendering the chat around a still draft must not either.
    pill.style.minHeight = "";
    const height = pill.offsetHeight;
    if (height !== pillHeight.current) {
      pillHeight.current = height;
      onResize();
    }
  }, [onResize]);

  // Layout, not paint: the measurement both chooses a layout and sizes the field, so it has to land
  // before the frame that shows the new character rather than one frame after it.
  useLayoutEffect(measure, [text, measure]);

  // The other thing that changes the answer is the width, and the width can move with the draft
  // standing still. Nothing in this component would notice: `text` is what re-runs the measurement,
  // so a narrower panel left BOTH readings computed for the old one, the field scrolled inside a
  // box sized for a line that no longer fits and the pill still inline with a draft that now wraps
  // (traced at 900x900: a one-line draft measured at 34px stayed at 34px with `scrollHeight` at 50
  // after the viewport went to 380px, and one further keystroke repaired it). The body's own window
  // is fixed and cannot resize, so this is not reachable there today, but the panel is
  // `min(560px, 92vw)` and every other way that number can move (a zoom, a resizable window, a
  // second platform) arrives through this same event.
  useEffect(() => {
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure]);

  const submit = () => {
    if (busy) {
      return;
    }
    onSubmit(text);
    setText("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const live = text.trim().length > 0 && !busy;

  return (
    <div ref={pillRef} className={`composer${stacked ? ` ${STACKED}` : ""}`}>
      <textarea
        ref={fieldRef}
        className="field"
        value={text}
        onChange={(event) => setText(event.target.value)}
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
