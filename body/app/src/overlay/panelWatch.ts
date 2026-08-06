// The watch the panel keeps on its own box, for the resizes nothing else announces.
//
// `usePanelMotion` places the panel on renders of `Panel`, on both ends of a section's roll, and on
// a window resize. Content that resizes the panel without any of those leaves the last placement
// standing, and the panel's `auto` height simply follows in the frame the content lands, bottom edge
// pinned, with no ease at all: a row released at the end of its exit is that shape (the release is
// state inside the list, not above it), and so is any content that settles after the render that
// brought it.
//
// A draft growing a line USED to be the first and largest of those cases, and is no longer one at
// all: the composer's text is state above the composer now (`drafts.ts`), so a keystroke renders
// `Panel` and its own layout effect places the panel, before paint and in the same commit that grew
// the pill. The ease is unchanged by the move, having always been the same `place`, and was
// re-measured after it at 640x720 with the reminder stack acked: a Shift+Enter that restacks and
// adds a line at once runs 184, 181.17, 168.08, 150.48, 140.5, 135.36, 132.88, 132.03, 132, against
// the 184, 181.14, 168.08, 150.41, 140.5, 135.34, 132.88, 132.03, 132 the observer used to drive.
// What the observer does with those keystrokes now is nothing, by the third rule below: the
// notification it gets one frame later finds the height that placement already chose.
//
// A `ResizeObserver` on the panel closes that gap, and the whole design of it is what it must NOT
// react to, because every placement resizes the element being watched.
//
// **A roll owns the height.** While a section inside is animating its own height, the panel's `auto`
// height follows it frame by frame, which is one notification per frame for the length of the roll
// (measured at 900x900 over the demo's reminder pull: 19 notifications across a 300ms roll). Placing
// on those would put the panel's own arithmetic against a height that is mid-animation by
// construction, and the ride-along has already taken the bottom edge to where the roll will leave
// it.
//
// **A move of the panel's own is asked a different question.** The panel's ease is a height
// animation on this same element, so it is also one notification per frame (18 across one 380ms
// move in the same trace), and the animation overrides the used height, so content growing inside
// the panel changes nothing the box can show. Answering the box would feed the observer its own
// output: each notification would cancel the running ease to measure the natural box and start
// another, sixty times a second. Refusing the box instead made the resize wait for the move, which
// it did until 2026-08-06, at a measured cost of up to a whole move's length of latency. So the
// watch asks what the panel WOULD be (`panelMemory.naturalHeightOf`), which the ease does not move
// and content does, and a growth that lands mid-move redirects that move from where the eye has it
// instead of queueing behind it.
//
// **A reading with nothing behind it is answered with nothing.** The question each time is whether
// the panel wants a height other than the one it was last placed for (`Memory.placedFor`), and the
// answer is no for every notification a placement raised by resizing the element it was placing.
// That is what settles the callback rather than letting it chase the box it just moved: a render
// that grew the panel is answered by the placement inside that render, and the notification it
// raises one frame later finds the height that placement chose already standing. Every keystroke in
// the composer now takes exactly this path, which is why moving the draft into the reducer cost the
// panel no motion and raised no loop error (measured over a draft typed character by character, a
// restack, a paste to the field's ceiling, a swap in and out of the chat holding it, and a send, at
// both viewports: zero).
//
// What is left is exactly the case the observer is for: the panel's content changed the height it
// wants, whether or not something is already moving it there.
//
// **And the watch is lifted for the frame the panel writes in.** Placing is itself a resize of the
// element being watched: the ease starts at the height the panel HAD, so the box the notification
// reported is not the box the frame paints. An observer whose callback resizes its own target is
// the one case the specification's depth rule cannot deliver, since the re-gathered observation is
// no deeper than the broadcast that caused it, so the notification is dropped and the page is told
// through the "loop completed with undelivered notifications" error. Measured over the demo, that
// was one error event per keystroke that grew the pill. Dropping the observation before placing and
// taking it up again on the next frame leaves nothing to re-gather, so the error never fires; the
// reading that arrives when the watch is taken up again is the height the placement just chose,
// which is the height it last looked at, so nothing is behind it.
//
// The ease itself is NOT a frame late for this. Traced at 640x720 over a Shift+Enter that restacks
// the pill: `requestAnimationFrame` runs before the resize observer steps, so a trace taken there
// reads 404 for the frame the character landed, while a probe reading the same frame AFTER the
// placement reads 352 with one animation attached. The frame paints the height the panel had and
// eases from it; nothing jumps and comes back.

import { MORPHING_ATTRIBUTE } from "./morph";
import { type Memory, heightOf, naturalHeightOf } from "./panelMemory";

/** Whether a section inside is rolling, which owns the height for as long as it runs. */
function rolling(element: HTMLElement): boolean {
  return element.querySelector(`[${MORPHING_ATTRIBUTE}]`) !== null;
}

/** The height the panel wants right now: what it would be with nothing animating it. Probed only
 *  while a move of its own is overriding the box, that being the one case the box cannot answer. */
function wanted(element: HTMLElement, memory: Memory): number {
  const moving = memory.running !== null && memory.running.playState === "running";
  return moving ? naturalHeightOf(element) : heightOf(element);
}

/**
 * Watch `element` and `replace` its placement whenever its own content resizes it.
 *
 * `replace` is the same placement the roll's end event drives, so the panel eases its content's
 * growth from wherever it is, exactly as it eases growth a render told it about.
 */
export function watchSize(element: HTMLElement, memory: Memory, replace: () => void): () => void {
  let rearm: number | null = null;
  const observer = new ResizeObserver(() => {
    if (rolling(element)) {
      return;
    }
    if (wanted(element, memory) === memory.placedFor) {
      return;
    }
    observer.unobserve(element);
    replace();
    rearm = requestAnimationFrame(() => {
      rearm = null;
      observer.observe(element);
    });
  });
  observer.observe(element);
  return () => {
    if (rearm !== null) {
      cancelAnimationFrame(rearm);
    }
    observer.disconnect();
  };
}
