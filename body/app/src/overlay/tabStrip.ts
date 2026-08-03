/** Where a key takes a strip from the tab it is on, or `null` for a key the strip does not answer.
 *  The arrows wrap, because on a strip of two, stopping at the ends would leave one arrow doing
 *  nothing half the time; Home and End are absolute, so they do not. */
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
