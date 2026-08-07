// Where the caret goes when a section the reader opened closes again. No chat arrived and no row
// moved: the whole section goes and takes every control in it, so the caret is handed to the
// section's anchor, and only when the caret was inside the section.

import { type RefObject, useLayoutEffect, useRef } from "react";

/** Hand the caret to the control a closing section leaves the reader on, without scrolling. Called
 *  directly by a gesture whose own section is unmounted in the commit it runs in, which is what an
 *  example chip on the empty state does. */
export function handOff(anchor: RefObject<HTMLElement | null>): void {
  anchor.current?.focus({ preventScroll: true });
}

/** Give a section the caret rule for its own closing. `open` is the section's state, not its
 *  presence: it stays mounted for the length of its closing roll, so it sees the close with its
 *  controls still on the page. A close that came with a chat is the arrival rule's business. */
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
    // on the page here, and a caret on `<body>` is a "no" with no special case.
    if (section.current?.contains(document.activeElement) === true) {
      handOff(anchor);
    }
  }, [open, arrival, section, anchor]);
}
