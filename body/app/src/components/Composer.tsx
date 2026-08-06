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
  /** The field itself, held by the view above so that the panel's other surfaces can hand the
   *  caret back to the conversation. The reminder stack is the one that needs it: acking its last
   *  row takes the whole section away, so the caret has nowhere in that list to go and comes here,
   *  where a summon lands anyway (`overlay/rowCaret.ts`, `ChatView`). Always attached, this
   *  component being mounted with the panel and never unmounted. */
  readonly field: MutableRefObject<HTMLTextAreaElement>;
  readonly busy: boolean;
  /** What this conversation is holding, unsent. The field is CONTROLLED by it rather than keeping
   *  its own copy, so a chat arriving is handed its own text by the same render that swaps the
   *  transcript: nothing here has to notice a swap, nothing parks anything on the way out, and
   *  there is no frame in between showing the wrong conversation's sentence (`overlay/drafts.ts`). */
  readonly draft: string;
  /** Every keystroke, parked under the chat on screen. Called with the field's raw value. */
  readonly onDraft: (text: string) => void;
  /** Which conversation this field is sitting in (`OverlayState.arrival`), or null while the panel
   *  is shut or the console is over the chat. Every change to it is a landing, and the field takes
   *  focus on each: null to a number is a summon or a return from the console, and one number to
   *  the next is a chat arriving under an open panel. */
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

/** The prompt input: Enter sends, Shift+Enter newlines, and the field grows with its content
 *  up to a few lines. Focus lands here whenever the panel opens (design/overlay-ux.md §7) and
 *  whenever another conversation arrives on it. While a turn streams the send button becomes a
 *  stop that cancels it (§3).
 *
 *  It holds no text of its own. What is typed here belongs to the conversation it was typed into
 *  and is kept there (`overlay/drafts.ts`), which is what makes a swap arriving with somebody
 *  else's half-typed sentence in the field impossible rather than merely unlikely: this component
 *  renders the chat on screen, and there is no second copy anywhere to fall out of step with it.
 *
 *  Past one line the pill restacks: on a single line the button is a flex sibling of the field,
 *  which is fine, but it reserves its column down the WHOLE pill, so every wrapped line stopped
 *  44px short of the right edge for no visible reason and the button floated alone at the bottom
 *  of a tall empty column. Stacked, the text uses the full width and the button sits under it,
 *  right aligned, where the eye already looks for it. Both layouts leave the button in the same
 *  corner of the same content box, one as the last item of a bottom-aligned row and one as the
 *  last row of a column, so the switch never moves it: traced character by character over two
 *  lines, its rect was identical in all 183 samples. */
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
  // Both are always mounted with the panel, so the refs are set before any effect runs. The field's
  // is the view's (see the prop), the pill's is this component's own.
  const pillRef = useRef<HTMLDivElement>(null!);
  // The pill's last measured height, so the container hears about a resize and not about a
  // keystroke. Starts at 0, which the first measurement is free to disagree with.
  const pillHeight = useRef(0);

  // WHERE THE CARET IS AFTER THE CONVERSATION CHANGES. A summon lands here, and so does a chat
  // arriving under an already open panel, which is one rule and not two: the reader is put in the
  // conversation on screen, in the one control that is about to be useful, and the field is never
  // unmounted so it is always there to take it. Three gestures needed it. A switcher row, a
  // reminder card's open control and a delete confirm each sit inside a section the swap takes
  // away, so the control that was pressed stopped existing (a leaving row goes `inert` at once, a
  // closing list unmounts its rows when the roll ends) and focus fell to `<body>`, outside the
  // panel and one Tab from the top of the page.
  //
  // At the arrival and not at the end of the roll. The swap is one commit, so moving here means
  // focus has already left the doomed control before its section starts rolling, rather than
  // riding 300ms on an element that is on its way out; and the roll is the panel's own movement,
  // which a focus landing in the middle of would be measured against.
  useEffect(() => {
    if (arrival !== null) {
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
  }, [arrival]);

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
  // before the frame that shows the new character rather than one frame after it. A RESTORED draft
  // is the same question asked of a whole sentence at once, and it is asked in the commit that
  // swapped the chat: the pill is already its restored height when the panel places itself in the
  // same commit (a parent's layout effect runs after its children's), so the panel eases to a
  // height that has the draft in it rather than easing twice.
  useLayoutEffect(measure, [draft, measure]);

  // The other thing that changes the answer is the width, and the width can move with the draft
  // standing still. Nothing in this component would notice: the draft is what re-runs the measurement,
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
      {/* THE CARET LANDS AT THE END OF A RESTORED DRAFT, which is the field's own answer and the
          one worth having: coming back to a half-typed thought is coming back to finish it, so the
          caret is where the next character goes. Assigning a textarea's value puts the selection
          at its end, and that assignment is exactly what a swap does here (the value differs, so
          React writes it; a keystroke's does not, so it does not, which is what leaves a caret
          typing mid-sentence alone). Focus arrives after it in the same commit, so the two agree. */}
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
