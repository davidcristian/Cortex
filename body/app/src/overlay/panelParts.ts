// What a placement asks the panel's own tree about: the section it leaves out of the height it
// centres on, how far short of its tallest shape the view falls, and the scroll positions its
// measurement costs. They live here because `panelPlacement` and `panelRoll` both need them.

import { MORPHING_ATTRIBUTE, TAB_SLACK_ATTRIBUTE } from "./morph";
import { heightOf } from "./panelMemory";

/** A section the panel leaves out when it centres itself, in the view being placed. The reminder
 *  stack can be two rows or five, so centring on it would put the conversation wherever the day's
 *  reminders leave it. Only an aside in the view being placed counts. */
const ASIDE = ".view:not(.out) .collapse.aside";

/** Every box inside the panel that scrolls: the conversation, and a console tab's rows. Written
 *  out rather than found, because finding them means reading `scrollTop` off every node in the
 *  panel on every token of a stream. A new scrolling box belongs in this list. */
const SCROLL_BOXES = ".history, .rows";

/** How tall the aside will be once everything settles: the height it is rolling to while it rolls,
 *  and the height it has otherwise. Reading the roll's target rather than the box is what lets the
 *  slide during a roll count an aside the same way the placement after the roll counts it. */
export function asideHeight(element: HTMLElement): number {
  const aside = element.querySelector<HTMLElement>(ASIDE);
  if (aside === null) {
    return 0;
  }
  const rolling = aside.getAttribute(MORPHING_ATTRIBUTE);
  return rolling === null ? heightOf(aside) : Number(rolling);
}

/** The height the panel centres on, which is not always the height it has: everything but the
 *  aside. One function with two callers on purpose, so an arrival and the placement that follows
 *  it cannot disagree about where the panel's middle is. */
export function centringHeight(element: HTMLElement, height: number): number {
  return height - asideHeight(element);
}

/** How far the view arriving falls short of the tallest shape it can take, which it publishes
 *  itself; 0 for a view of one shape. Added to the bottom edge on the way in, so the top edge
 *  arrives where the tallest shape would put it and a shorter tab ends higher. */
export function tabSlack(element: HTMLElement): number {
  const published = element
    .querySelector(`.view:not(.out) [${TAB_SLACK_ATTRIBUTE}]`)
    ?.getAttribute(TAB_SLACK_ATTRIBUTE);
  return published === null || published === undefined ? 0 : Number(published);
}

/** Take the scroll positions the panel's own measurement is about to cost, and give them back. The
 *  panel measures itself by growing to the loosest cap any edge could allow, and the engine clamps
 *  a scroll box that outgrew its range, which putting the real cap back does not undo. */
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
