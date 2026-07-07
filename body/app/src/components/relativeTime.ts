// A compact relative timestamp for the chat switcher. `now` is passed in rather than read here,
// so the function is deterministic under test.

const MINUTE = 60;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export function relativeTime(unixMs: number, now: number): string {
  const seconds = Math.max(0, Math.round((now - unixMs) / 1000));
  if (seconds < MINUTE) {
    return "just now";
  }
  if (seconds < HOUR) {
    return `${Math.floor(seconds / MINUTE)}m ago`;
  }
  if (seconds < DAY) {
    return `${Math.floor(seconds / HOUR)}h ago`;
  }
  return `${Math.floor(seconds / DAY)}d ago`;
}
