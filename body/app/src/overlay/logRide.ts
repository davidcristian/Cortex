// The scroll the history makes alongside a section rolling open or shut inside it. A roll moves
// three things: the section owns its own height (`morph.ts`), the panel takes its bottom edge along
// with it (`panelRide.ts`), and this is the third, the log underneath.
//
// A Thoughts trace rolls open in the middle of a settled reply, above the bubble it belongs to.
// Below the panel's ceiling that costs nothing: the panel grows by exactly what the trace takes, the
// history grows with it, and the log's scroll range never changes. At the ceiling the panel has
// nothing left to give, so the growth goes into the scroll range instead and the end of the reply
// slides out under the composer. The panel's chrome produces the same defect from the other side:
// the switcher list and the reminder stack roll outside the history, so at the ceiling their growth
// comes out of the log's window rather than out of the log's content, the range grows because the
// box shrank, and the reader is carried off the end of the reply just the same. Those rolls are
// heard on the column the panel renders the view into, their start event never reaching the box
// (`useLogScroll`), and the cap below is the only thing here that asks which kind of roll it is.
//
// The rule is the tail pin, held across a roll. Whether the reader is at the tail is the claim the
// log already keeps and already restores (`useLogScroll`), and the reader at the tail is the one
// this happens to. So while they are there, the log holds the same distance from the end of the
// content for every frame of the roll, and the growth comes out of the scroll rather than out of the
// reply. A reader who has scrolled up is left alone, which is the disclosure's own default and the
// right behaviour for them: a section growing pushes only what is below it, and what is below it is
// not where they are reading. Closing is the same rule and lands back on the same pixel, so a reader
// who opened a trace and shut it again is where they started. That half is also what `.history`
// gave up when it turned scroll anchoring off: anchoring eased `scrollTop` down with a shrink to
// hold the visible content still, which is what holding the distance from the tail does here.
//
// The claim is measured here rather than remembered. The log's own copy of it is refreshed from
// scroll events, and a roll changes the answer without one: a trace opened at the ceiling takes the
// tail 76px away with no scroll at all, so the remembered answer still reads "at the tail" when the
// reader is not, and a round trip that should have been reversible left the reader 76px off where
// they started. Read off the box on the roll's own first frame, both directions answer for the
// state they are actually in.
//
// The cap is that the reader keeps what they opened. Holding the tail through a trace taller than
// the window would scroll the trace's own top edge off the screen and leave them reading its bottom
// half, so the ride stops at the frame the trace reaches the top of the window and gives back only
// as much of the reply as still fits under it.
//
// There is no clock here and no curve. The scroll is recomputed from the box on every frame of the
// roll, and the box is being resized by the roll's own height animation, so the scroll inherits the
// roll's timing rather than having to agree with it: neither `MORPH_ROLL_MS` nor `EASING` is read in
// this file. It is also why `prefers-reduced-motion` needs nothing, a roll under it being no motion
// at all: `Collapse` commits the end state without announcing a start, and the log holds still
// exactly as it did before the disclosure animated at all.
//
// The ADR-0035 addendum of 2026-08-03 carries the traces behind every claim above.

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
 *
 * The cap applies only to a section inside the box. A section in the panel's chrome takes its room
 * from the log's window rather than from the log's content, so there is nothing in here for the
 * reader to be carried away from: the switcher list they just opened is above this box and stays
 * where the panel put it, whatever the log does underneath. Read as room an outside section is worse
 * than irrelevant, its top edge sitting above the box's for every frame of the roll, so the
 * subtraction is negative, the floor turns it into no room at all, and the cap freezes the ride at
 * the position it started from (ADR-0035, 2026-08-03, traces that at 640x720).
 */
function stopAt(box: HTMLElement, section: HTMLElement, tail: number): number {
  const hold = box.scrollHeight - box.clientHeight - tail;
  if (!box.contains(section)) {
    return hold;
  }
  const room = section.getBoundingClientRect().top - box.getBoundingClientRect().top;
  // Room is spent rather than kept: a section already above the window's top edge caps the ride
  // where it stands, since scrolling further down carries the reader away from what they opened.
  const cap = box.scrollTop + Math.max(room, 0);
  // The floor here matches the engine's: a position past either end of the range is clamped to it,
  // which is also what the read-back below is for.
  return Math.min(hold, cap);
}

/**
 * Hold `box`'s distance from the end of its content for every frame of the roll now running in
 * `section`, for a reader already `within` px of that end. Returns the way to call the ride off.
 *
 * `within` is the log's own pin threshold, passed in rather than read from here: how close to the
 * end still counts as reading it is the log's policy (`useLogScroll`), and this file only applies
 * it. The two have to be the same number, or a reply landing mid-roll would follow the tail while
 * the roll held a different one.
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
      // it is rolling from, so this reading is the "before" one even though layout has held the
      // section's finished content since the commit that mounted it. No arithmetic has to guess
      // what the panel is about to absorb: the ride reads what the box actually becomes, frame by
      // frame, and below the ceiling that is nothing at all. It is also the last moment the
      // reader's own distance from the end can still be read, which is why the pin is tested here
      // and not by the caller.
      tail = range - box.scrollTop;
      if (tail > within) {
        frame = null;
        return;
      }
    } else if (Math.abs(box.scrollTop - Math.min(wrote, range)) >= MIN_DELTA_PX) {
      // Someone else has the scroll: the reader's wheel, or the tail pin answering a reply that
      // landed mid-roll. Either of them outranks this ride, which stops rather than competing for
      // the scroll position. Compared against what was last written rather than against a target,
      // and clamped to the range the box has now, because a closing roll shortens the content under
      // a scroll position the engine then clamps for itself, which is the box moving and not the
      // reader.
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
