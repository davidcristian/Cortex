// What a placement has to ask the panel's own tree about: the section it leaves out of the height
// it centres on, how far short of its tallest shape the view on screen falls, and the scroll
// positions its measurement is about to cost. Read-only probes over the DOM, with no arithmetic and
// no memory of their own.
//
// They live here rather than in `panelPlacement` because `panelRide` needs the same answers and
// `panelPlacement` already imports `panelRide`: asking the same question two ways is how the
// ride-along's prediction and the placement that follows it came to disagree.

import { MORPHING_ATTRIBUTE, TAB_SLACK_ATTRIBUTE } from "./morph";
import { heightOf } from "./panelMemory";

/** A section the panel leaves out when it centres itself, in the view being placed. The reminder
 *  stack arrives with the summon and can be two rows or five, so centring on it puts the
 *  conversation wherever the day's reminders happen to leave it. The chat centres on itself and the
 *  stack grows it upward from there, the way every other arrival does.
 *
 *  Only an aside in the view being placed counts. The view being left is still in the DOM for one
 *  morph, and a stack belonging to it was being subtracted from the height of the view arriving,
 *  which has no stack and never did. Measured at 640x720 entering the console over an empty chat
 *  with three reminders up: the console is 347px tall and was centred as though it were 155, which
 *  put it 96px above the middle of the screen and, since the ceiling is measured from the edge it
 *  sits on, capped it at 351px instead of 448. The console then had four spare pixels in it, and
 *  anything added to a tab scrolled rather than fitting. */
const ASIDE = ".view:not(.out) .collapse.aside";

/** Every box inside the panel that scrolls: the conversation, and a console tab's rows. Written out
 *  rather than discovered, because discovering it means reading `scrollTop` off every node in the
 *  panel on every token of a stream. A new scrolling box in the panel belongs in this list. */
const SCROLL_BOXES = ".history, .rows";

/**
 * How tall the aside will be once everything settles: the height it is rolling to while it rolls,
 * and the height it has otherwise. Zero when the view being placed has no aside at all.
 *
 * Reading the roll's target rather than the box is what lets the ride-along count an aside the same
 * way the placement after the roll counts it. Counting the box instead would have the ride-along
 * subtract whatever fraction of the stack had rolled in by that frame, which is a different number
 * every time it is asked.
 */
export function asideHeight(element: HTMLElement): number {
  const aside = element.querySelector<HTMLElement>(ASIDE);
  if (aside === null) {
    return 0;
  }
  const rolling = aside.getAttribute(MORPHING_ATTRIBUTE);
  return rolling === null ? heightOf(aside) : Number(rolling);
}

/** The height the panel centres on, which is not always the height it has: everything but the
 *  aside. One function with two callers on purpose, the measured height in `panelPlacement` and the
 *  predicted one in `panelRide`, so an arrival and the placement that follows it cannot disagree
 *  about where the panel's middle is. */
export function centringHeight(element: HTMLElement, height: number): number {
  return height - asideHeight(element);
}

/** How far the view arriving falls short of the tallest shape it can take, which it publishes
 *  itself (`TAB_SLACK_ATTRIBUTE`); 0 for a view of one shape, which is every view but the
 *  console. Added to the bottom edge on the way in, so the top edge lands where the tallest shape
 *  would put it and a shorter tab ends higher instead of starting lower. Without it the console's
 *  strip sat at two different heights depending on which tab it was opened on, and the user
 *  caught it: the shortcuts tab opened lower than the appearance tab. */
export function tabSlack(element: HTMLElement): number {
  const published = element
    .querySelector(`.view:not(.out) [${TAB_SLACK_ATTRIBUTE}]`)
    ?.getAttribute(TAB_SLACK_ATTRIBUTE);
  return published === null || published === undefined ? 0 : Number(published);
}

/**
 * Take the scroll positions the panel's own measurement is about to cost, and give them back.
 *
 * The panel measures itself by growing to the loosest cap any edge could allow and reading what it
 * becomes (`openHeight`). A scroll box inside a taller panel is a taller box, and the engine answers
 * a box that has outgrown its own scroll range by clamping it to the range it now has, which putting
 * the real cap back does not undo. So the panel's own measurement walks the log up under the reader.
 *
 * Traced at 60Hz at 640x720 through a streamed reply, wheeling 60px up from the tail: `scrollTop`
 * read 312, then 252 the frame the wheel landed, then 215 two frames later with nothing else
 * touching it, 215 being exactly the deepest a 390px window can scroll a 605px log. Every token did
 * it again, which is the reported symptom that the history cannot be scrolled while a reply
 * streams. The same clamp lands on the way back from the console, where it took the position
 * `ChatView` had just restored and left the log 97px off the tail rather than where the reader was.
 */
export function holdScroll(element: HTMLElement): () => void {
  const boxes = [...element.querySelectorAll<HTMLElement>(SCROLL_BOXES)].map(
    (box) => [box, box.scrollTop] as const,
  );
  return () => {
    for (const [box, top] of boxes) {
      box.scrollTop = top;
    }
  };
}
