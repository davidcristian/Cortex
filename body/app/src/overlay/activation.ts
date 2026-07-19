// Summoning the overlay, made robust against arriving before anyone is listening.
//
// The host emits an activation on the global hotkey and the browser build self-summons on load;
// both reach the app as a DOM event on `window`. A plain event is delivered only to listeners
// that already exist, and the app's listener is attached in a passive effect, which React flushes
// AFTER paint. Measured in a browser: the self-summon dispatched at t=102ms and the listener
// attached at t=104ms, so the overlay never opened and `npm run dev` came up to an empty stage.
// The same race drops a real hotkey press that lands while the webview is still mounting, which
// is the cold-start case where the first press is the one the user cares about.
//
// So an activation is treated as a FACT rather than as a moment: it is recorded as pending and
// announced, and whoever attaches next takes the pending one. Both paths clear the flag, so a
// later remount cannot replay a summon that has already been answered.

/** The DOM event both the host bridge and the browser self-summon dispatch on `window`. */
export const ACTIVATE_EVENT = "cortex:activate";

let pending = false;

/** Ask for the overlay: record the request, then announce it to whoever is already listening. */
export function requestActivation(): void {
  pending = true;
  window.dispatchEvent(new Event(ACTIVATE_EVENT));
}

/** Take the outstanding activation, if any. Answering one consumes it, so it fires once. */
export function takePendingActivation(): boolean {
  const outstanding = pending;
  pending = false;
  return outstanding;
}
