// The scroll the history makes alongside a section rolling open or shut inside it. A roll moves
// three things: the section owns its own height (`morph.ts`), the panel takes its bottom edge along
// with it (`panelRide.ts`), and this is the third, the log underneath.
//
// A Thoughts trace rolls open in the middle of a settled reply, above the bubble it belongs to.
// Below the panel's ceiling that costs nothing: the panel grows by exactly what the trace takes, the
// history grows with it, and the log's scroll range never changes. At the ceiling the panel has
// nothing left to give, so the growth goes into the scroll range instead and the end of the reply
// slides out under the composer. Traced at 60Hz at 640x720 on a history full enough to hold the
// panel at its ceiling: the trace was 76px, the disclosure's top edge held at 262px for every frame
// of the roll, and the distance from the log's bottom edge to the end of the reply went 3px to 79px,
// which is the last two lines of the answer gone.
//
// **The rule is the tail pin, held across a roll.** Whether the reader is at the tail is the claim
// the log already keeps and already restores (`useLogScroll`), and the reader at the tail is the one
// this happens to. So while they are there, the log holds the same distance from the end of the
// content for every frame of the roll, and the growth comes out of the scroll rather than out of the
// reply. A reader who has scrolled up is left alone, which is the disclosure's own default and the
// right one for them: a section growing pushes only what is BELOW it, and what is below it is not
// where they are reading.
//
// **That claim is measured here rather than remembered.** The log's own copy of it is refreshed from
// scroll events, and a roll is precisely the thing that falsifies it without one: a trace opened at
// the ceiling takes the tail 76px away with no scroll at all, so the remembered answer still says
// "at the tail" when the reader plainly is not. Traced at 640x460, where the history is 121px and the
// disclosure sits above the window: opening on the remembered claim did nothing (the cap below), and
// CLOSING on the same stale claim eased the log 76px, so a round trip that had been exactly
// reversible left the reader 76px off where they started. Read off the box on the roll's own first
// frame, both directions answer for the state they are actually in.
//
// **One rule, both directions.** Closing is the same sentence and lands back on the same pixel, so
// the reader who opened a trace and shut it again is exactly where they started. It is also the half
// the engine had been getting right before `.history` turned scroll anchoring off: with the trace
// scrolled off the top of the window, anchoring eased `scrollTop` down with the shrink to hold the
// visible content still, which is what holding the distance from the tail does here, deliberately
// and in code.
//
// **The cap is that the reader must keep what they opened.** Holding the tail through a trace taller
// than the window would scroll the trace's own top edge off the screen and leave them reading its
// bottom half, so the ride stops at the frame the trace reaches the top of the window and gives back
// only as much of the reply as still fits under it. Following the tail without that cap is the fix
// that looks right and is not. Traced at 640x600, where the trace's own top edge sits 58px below the
// top of a 206px window: the ride spends exactly those 58px, stops at t=181ms with the whole trace
// in view from its first line, and lets the last 21px of the growth go into the scroll as before.
//
// **There is no clock here and no curve.** The scroll is recomputed from the box on every frame of
// the roll, and the box is being resized by the roll's own height animation, so the scroll inherits
// the roll's timing by construction rather than by agreeing with it. Neither `MORPH_ROLL_MS` nor
// `EASING` is read in this file, which is the strongest form of sharing them. It is also why
// `prefers-reduced-motion` needs nothing: a roll under it is not a motion at all, `Collapse` commits
// the end state without announcing a start, and the log holds still exactly as it did before the
// disclosure learned to move.

import { MIN_DELTA_PX, MORPHING_ATTRIBUTE } from "./morph";

/**
 * Where `box` must sit for `tail` px of content to stay below its bottom edge, capped so that
 * `section`'s own top edge stays on screen.
 *
 * Measured on the rolling section rather than on the block around it. In the one case where the cap
 * binds at all, a trace tall enough to fill the window, the control that opened it ends a row above
 * the top edge, and anchoring on that block instead would keep it; it would also read a room of zero
 * for a section that is the scroll box's own child, which makes the rule depend on how much markup
 * happens to sit between the two. The section is the element the roll names.
 */
function stopAt(box: HTMLElement, section: HTMLElement, tail: number): number {
  const room = section.getBoundingClientRect().top - box.getBoundingClientRect().top;
  // Room is spent, not kept: a section already above the window's top edge caps the ride where it
  // stands, since scrolling further down carries the reader away from the thing they just opened.
  const cap = box.scrollTop + Math.max(room, 0);
  // The floor is the engine's: a position past either end of the range is clamped to it, which is
  // also what the read-back below is for.
  return Math.min(box.scrollHeight - box.clientHeight - tail, cap);
}

/**
 * Hold `box`'s distance from the end of its content for every frame of the roll now running in
 * `section`, for a reader already `within` px of that end. Answers the way to call the ride off.
 *
 * `within` is the log's own pin threshold, passed in rather than read from here: how close to the
 * end still counts as reading it is the log's policy (`useLogScroll`), and this is the mechanism
 * that policy is spent on. The two have to be the same number, or a reply landing mid-roll would
 * follow the tail while the roll held a different one.
 */
export function rideTail(box: HTMLElement, section: HTMLElement, within: number): () => void {
  // The distance being held, learned on the first frame rather than given: see below.
  let tail: number | null = null;
  // What this ride last put on the box, so a scroll that did not come from here can be told apart
  // from one that did.
  let wrote = 0;
  let frame: number | null = null;
  const step = (): void => {
    const range = box.scrollHeight - box.clientHeight;
    if (tail === null) {
      // The first frame is the roll's own frame zero, where the section still stands at the height
      // it is rolling FROM. So this reading is the "before" one, even though layout has held the
      // section's finished content since the commit that mounted it, and the ride needs no
      // arithmetic to guess what the panel is about to absorb: it reads what the box actually
      // becomes, frame by frame, and below the ceiling that is nothing at all. It is also the only
      // moment the reader's own distance from the end can be honestly asked for, which is why the
      // pin is tested here and not by the caller.
      tail = range - box.scrollTop;
      if (tail > within) {
        frame = null;
        return;
      }
    } else if (Math.abs(box.scrollTop - Math.min(wrote, range)) >= MIN_DELTA_PX) {
      // Someone else has the scroll: the reader's wheel, or the tail pin answering a reply that
      // landed mid-roll. Either of them outranks this, and a ride that fought the reader would be a
      // worse thing to have built than the 76px it exists to save. Compared against what was last
      // written rather than against a target, and clamped to the range the box has NOW, because a
      // closing roll shortens the content under a scroll position the engine then clamps for
      // itself, which is the box moving and not the reader.
      frame = null;
      return;
    } else {
      box.scrollTop = stopAt(box, section, tail);
    }
    // Read back rather than remembered: the engine clamps a scroll position to the range it has, so
    // what was asked for and what the box took are not always the same number.
    wrote = box.scrollTop;
    // Work first and decide after, so the frame that finds the roll over has already settled the
    // scroll on the height the roll ended at: `Collapse` clears the attribute before it says the
    // roll ended. The section can also leave the tree mid-roll with the attribute still on it, a
    // chat switched while a trace rolls unmounting the whole message, and a loop reading a detached
    // tree would never stop.
    frame =
      section.isConnected && section.hasAttribute(MORPHING_ATTRIBUTE)
        ? requestAnimationFrame(step)
        : null;
  };
  frame = requestAnimationFrame(step);
  return () => {
    if (frame !== null) {
      cancelAnimationFrame(frame);
      frame = null;
    }
  };
}
