// THE KEYS A TAB STRIP ANSWERS, AS ONE MAP, AWAY FROM THE VIEW THAT SPENDS THEM.
//
// The WAI-ARIA tab pattern is specific about this, and the console's strip carried the roles for it
// without carrying the keys: `role="tablist"`, a `role="tab"` per face, `aria-selected` on the one
// showing, and Left and Right doing nothing at all. What the pattern asks for is that the arrows
// move along the strip, that Home and End go to its ends, and that the strip is ONE stop in the
// page's tab order rather than one stop per tab, which is the roving `tabindex` the view writes.
//
// The rules this map makes, both of which are choices rather than transcriptions:
//
// The arrows WRAP and Home and End do not. Wrapping is what the practice recommends, and on a strip
// of two it is what makes the arrows worth pressing: stopping at the ends would leave Right a no-op
// half the time, which reads as a key that is broken rather than as a strip that has an end. Home
// and End are absolute by their own meaning, so there is nothing for them to wrap around; End on
// the last tab is the last tab.
//
// The strip answers Left and Right and NOT Up and Down. It is a horizontal strip, which is the
// practice's own condition for that, and the overlay spends Ctrl with the vertical arrows on
// cycling chats; a strip that also answered them would be a second meaning for one gesture,
// separated only by a modifier.

/**
 * Where a key takes a strip from the tab it is on, or `null` for a key the strip does not answer.
 *
 * Pure, and generic over what a tab is, so the strip's keyboard is one map that can be read in one
 * place and a second strip is a call rather than a copy. Returning the tab rather than its index
 * keeps the caller out of index arithmetic it would have to bound-check to no purpose.
 *
 * A strip with nothing on it answers no key, which is the one edge here: `indexOf` reports -1, the
 * arithmetic below is still total, and the lookup that follows finds nothing and says so.
 */
export function nextTab<T>(key: string, tabs: readonly T[], from: T): T | null {
  const at = tabs.indexOf(from);
  const last = tabs.length - 1;
  let to: number;
  switch (key) {
    case "ArrowRight":
      to = at === last ? 0 : at + 1;
      break;
    case "ArrowLeft":
      to = at === 0 ? last : at - 1;
      break;
    case "Home":
      to = 0;
      break;
    case "End":
      to = last;
      break;
    default:
      return null;
  }
  return tabs[to] ?? null;
}
