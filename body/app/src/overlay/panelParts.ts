
import { MORPHING_ATTRIBUTE, TAB_SLACK_ATTRIBUTE } from "./morph";
import { heightOf } from "./panelMemory";

/** A section the panel leaves out when it centres itself, in the view being PLACED. */
const ASIDE = ".view:not(.out) .collapse.aside";

/** Every box inside the panel that scrolls: the conversation, and a console tab's rows. Written out
 *  rather than discovered, because discovering it means reading `scrollTop` off every node in the
 *  panel on every token of a stream. A new scrolling box in the panel belongs in this list. */
const SCROLL_BOXES = ".history, .rows";

/**
 * How tall the aside will be once everything settles: the height it is rolling TO while it rolls,
 * and the height it has otherwise. Zero when the view being placed has no aside at all.
 */
export function asideHeight(element: HTMLElement): number {
  const aside = element.querySelector<HTMLElement>(ASIDE);
  if (aside === null) {
    return 0;
  }
  const rolling = aside.getAttribute(MORPHING_ATTRIBUTE);
  return rolling === null ? heightOf(aside) : Number(rolling);
}

/**
 * The height the panel centres ON, which is not always the height it HAS: everything but the
 * aside.
 */
export function centringHeight(element: HTMLElement, height: number): number {
  return height - asideHeight(element);
}

/**
 * How far the view arriving falls short of the tallest shape it can take, which it publishes
 * itself (`TAB_SLACK_ATTRIBUTE`); 0 for a view of one shape, which is every view but the console.
 */
export function tabSlack(element: HTMLElement): number {
  const published = element
    .querySelector(`.view:not(.out) [${TAB_SLACK_ATTRIBUTE}]`)
    ?.getAttribute(TAB_SLACK_ATTRIBUTE);
  return published === null || published === undefined ? 0 : Number(published);
}

/** Take the scroll positions the panel's own measurement is about to cost, and give them back. */
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
