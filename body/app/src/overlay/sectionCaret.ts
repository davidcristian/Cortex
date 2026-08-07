import { type RefObject, useLayoutEffect, useRef } from "react";

// WHERE THE CARET GOES WHEN A SECTION THE READER OPENED CLOSES AGAIN.
//
// Two rules stand beside this one and neither reaches it. A conversation arriving takes the caret to
// the composer (`OverlayState.arrival`, `Composer`), which answers every gesture that REPLACES the
// chat. A list that reshapes under the hand keeps the caret among its own rows, and hands it to the
// list's anchor when it runs out of them (`overlay/rowCaret.ts`), which answers a row changing
// shape, a row leaving, and a list emptying. A section the reader CLOSES is none of those: no chat
// arrived, no row moved, the whole section simply goes and takes every control in it. Measured at
// 900x900 with the caret on a resting row's pencil, `Ctrl+K` held the caret for the 300ms roll and
// read `<body>` at 353ms, which is the landing outside the panel that both rules above exist to
// abolish, and the same landing this key produced from inside a rename editor until the day before.
//
// SO A SECTION THE READER CLOSES HANDS THE CARET TO ITS ANCHOR, AND ONLY WHEN THE CARET IS INSIDE
// IT. The anchor is the control the section already carries for its emptied case, so "this list
// cannot keep the caret" has one answer rather than two: the header's chats button for the switcher,
// which is the control that closed the list and the control that would open it again, and the
// composer's field for a section whose work is over.
//
// THE GUARD IS WHY THIS IS A RULE AND NOT A LINE. `Ctrl+K` is a global key, pressed as often from
// the composer as from the list, and measured at HEAD it leaves a half-typed draft alone with its
// caret at offset 4 of "half a question". Moving the caret on every close would pull the reader out
// of a sentence to tell them a list they were not standing in has gone. It also makes the header's
// own chats button need no special case: pressing it focuses it first (measured, the pointer's
// press moving the caret out of the row and onto the button at 45ms), so the caret is already on
// the anchor by the time the close is decided and the rule finds nothing to do.
//
// AND IT STANDS DOWN WHEN A CHAT ARRIVED IN THE SAME COMMIT. Most of the ways the switcher closes
// are swap arms, not closes: a row selected, `Ctrl+N`, the header's pencil, the cycle keys, a
// reminder's open control. Those close the list AND raise `arrival`, and the caret belongs in the
// arriving conversation, so this rule defers to that one explicitly rather than by leaving the
// composer's effect to run later and win: two focus moves in one commit are two events a screen
// reader may read out, whichever of them the browser paints.

/**
 * Hand the caret to the control a closing section leaves the reader standing on.
 *
 * WITHOUT SCROLLING ANYTHING, the reason `overlay/rowCaret.ts` and the composer both give at length:
 * the panel clips its overflow, which makes it a scroll box the user can never scroll and the engine
 * can, and bringing a newly focused element into view is exactly when it does.
 *
 * Called directly by a gesture whose own section is unmounted in the commit it fires, where there is
 * nothing left for the hook below to look inside: the empty state's example chips are the one such
 * control the overlay has, and pressing one sends its prompt and takes the whole empty state away,
 * the reminder stack above it included (measured at 900x900: the caret read `<body>` at 39ms). The
 * field is where the answer to that prompt gets written, and where every other send leaves the
 * caret already.
 */
export function handOff(anchor: RefObject<HTMLElement | null>): void {
  anchor.current?.focus({ preventScroll: true });
}

/**
 * Give a section the caret rule for its own closing.
 *
 * `open` is the section's state, not its presence: a section is mounted for the length of its
 * closing roll (`Collapse`), so it hears the close with its controls still on the page and the
 * caret still on one of them, which is exactly what makes the guard below readable from the DOM.
 * `arrival` is `OverlayState.arrival`, and a close that came with a chat is that rule's business
 * (see the note above).
 *
 * A layout effect, at the commit that closes the section rather than at the end of its roll, which
 * is the call both neighbouring rules made and for the same reason: the control being aimed at has
 * been on screen all along, so there is nothing to wait for, and waiting would park the caret on
 * something rolling to nothing for 300ms.
 */
export function useSectionCaret(
  section: RefObject<HTMLElement | null>,
  anchor: RefObject<HTMLElement | null>,
  open: boolean,
  arrival: number,
): void {
  const was = useRef(open);
  const seen = useRef(arrival);
  useLayoutEffect(() => {
    const closing = was.current && !open;
    const arrived = seen.current !== arrival;
    was.current = open;
    seen.current = arrival;
    if (!closing || arrived) {
      return;
    }
    // Asked of the live DOM rather than tracked as the caret moves, because the section is still
    // standing here: `contains` of whatever holds focus is the whole question, and a null section
    // (or a caret on `<body>`, which no element contains) is a "no" without a special case.
    if (section.current?.contains(document.activeElement) === true) {
      handOff(anchor);
    }
  }, [open, arrival, section, anchor]);
}
