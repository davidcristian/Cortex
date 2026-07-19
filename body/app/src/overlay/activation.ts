// Summoning the overlay. A plain DOM event reaches only listeners that already exist, and the
// app's listener is attached after paint, so each activation is recorded as pending as well.

/** The DOM event both the host bridge and the browser self-summon dispatch on `window`. */
export const ACTIVATE_EVENT = "cortex:activate";

let pending = false;

/** Ask for the overlay: record the request, then announce it to whoever is already listening. */
export function requestActivation(): void {
  pending = true;
  window.dispatchEvent(new Event(ACTIVATE_EVENT));
}

/** Take the outstanding activation, if any. Answering one clears it, so it opens the overlay
 *  once. */
export function takePendingActivation(): boolean {
  const outstanding = pending;
  pending = false;
  return outstanding;
}
