// Which edge the panel holds. `panelPlacement` measures the element and plays the move; this is the
// rule it asks first, and the only thing in the panel's motion that is about the user's hand rather
// than about pixels.
//
// Four rules share one measurement:
//
//   1. ENTERING ANOTHER VIEW resizes it in place. Opening the console, or moving between its tabs,
//      resizes the panel to what that view needs from the bottom edge the chat is standing on, the
//      way growth inside a view does. It shipped sliding to the true middle of the screen instead,
//      and the user, having lived with it, chose the standing edge (2026-07-21); the slide stays
//      one flip away behind `VIEW_CHANGE_RECENTRES`, both settings under test.
//   2. COMING BACK TO THE CHAT restores it. The chat's own bottom edge is parked on the way out and
//      handed back on the way in, so a trip to the console and back leaves the conversation exactly
//      where the eye left it. With rule 1 holding the edge anyway, the park is a no-op today; it is
//      kept because it is what makes the return correct the moment the slide is switched back on.
//   3. GROWTH INSIDE THE CHAT pushes the top edge up. A reply arriving, the switcher list opening,
//      a new chat emptying the panel, the composer taking a second line: the bottom stays pinned
//      where it was, so the composer never slides out from under the hand that just typed into it.
//      Minting a new chat belongs here and not in rule 1: it is the same view with less in it.
//   4. A RESIZE INSIDE ANY OTHER VIEW pushes the bottom edge down instead, holding the top. Which
//      edge holds is decided by where the hand is, and the console's chrome is its tab strip, at
//      the top: changing tabs must not slide the strip out from under the cursor that clicked it.
//      Rule 3 is the same principle at the chat's other end. A view with more than one shape is
//      entered at the top its TALLEST shape would take (`tabSlack`), so that held top is the same
//      one whichever tab the console is opened on, and a shorter tab ends higher rather than
//      starting lower.
//
// A summon is outside all four: for as long as the panel is arriving it centres on whatever it
// currently is, so content that lands behind the summon (the reminder pull, a restored
// conversation) is the panel appearing with it rather than growth from an edge it was pinned to
// before it had any.

import { centred } from "./panelGeometry";
import { type Memory, type Placement, arriving } from "./panelMemory";

/** The view whose position is remembered across a trip to another one. */
const CHAT_VIEW = "chat";

/** Whether entering another view slides the panel to the true middle of the screen, or keeps the
 *  bottom edge it is standing on and resizes in place. The slide shipped first; the maintainer chose
 *  the standing edge after living with both (2026-07-21), and asked for the slide to stay a
 *  switch rather than a memory. `place` takes it as a defaulted argument so the tests hold both
 *  branches green, and flipping this constant is the whole change back. */
export const VIEW_CHANGE_RECENTRES = false;

/** Whether the panel is arriving in a view with more than one shape, which is the one render that
 *  hangs it from the top its tallest shape would take. Asked before `pinnedBottom` decides
 *  anything, because deciding is also what forgets which view the panel was in. */
export function entering(memory: Memory, at: Placement): boolean {
  return at.open && memory.view !== at.view && at.view !== CHAT_VIEW;
}

/**
 * Where the panel's bottom edge wants to be, before the ceiling has its say.
 *
 * Also updates the memory the next such decision reads: which view is on screen, and where the chat
 * was parked when it was left. A closed panel always re-centres, because it is about to be summoned
 * and should come back to the middle rather than to wherever the last conversation had pushed it.
 */
export function pinnedBottom(
  memory: Memory,
  at: Placement,
  viewport: number,
  centring: number,
  height: number,
  recentres: boolean,
): number {
  const changed = memory.view !== at.view;
  if (changed && memory.view === CHAT_VIEW) {
    memory.parked = memory.pinned;
  }
  memory.view = at.view;
  const shown = memory.shown;
  // Nothing on screen to hold on to yet: a first placement centres, whatever else is true.
  if (shown === null) {
    return centred(viewport, centring);
  }
  const parked = changed && at.view === CHAT_VIEW ? memory.parked : null;
  if (!at.open || at.recentre || arriving(memory, at) || (recentres && changed && parked === null)) {
    return centred(viewport, centring);
  }
  if (parked !== null) {
    return parked;
  }
  // A resize INSIDE a view other than the chat holds that view's TOP edge, so the growth happens
  // at the bottom. Which edge holds is decided by where the hand is: a console tab is changed
  // from the strip at the top, and that strip must not move out from under the cursor that just
  // clicked it. The chat is the other way round for the same reason, its composer being the edge
  // the hand is on, which is why rule 3 above pins its bottom. Entering a view is neither, and
  // keeps the edge it arrived on (rule 1): the opener that was clicked is down in the hint strip.
  if (!changed && at.view !== CHAT_VIEW) {
    return shown.bottom + shown.height - height;
  }
  return memory.pinned;
}
