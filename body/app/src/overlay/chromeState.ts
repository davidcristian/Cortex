import { type Notice, speak, switcherOpened } from "./notice";
import type { ConsoleTab, OverlayState } from "./overlayState";

// WHICH OF THE PANEL'S SECTIONS IS SHOWING.
//
// The switcher's list and the console's tabs are the two things the panel puts up around the chat
// without changing which conversation is in it, so they are one responsibility and it is not the
// conversation's. Split out of `overlayState.ts` when the switcher grew the rule below, which is
// the third such half beside the session switching and the turn fold, and for the same reason: the
// line cap is what keeps each of them explainable in one file.

/**
 * Whether the chat is the view a reader is actually looking at.
 *
 * Both of the overlay's chords stay live while it is not: `Ctrl+K` toggles the switcher from a
 * tucked panel and from behind an open console, and measured in Chromium both work exactly as they
 * do on the chat, the list mounting with its three rows and `aria-expanded` flipping to true. What
 * they do NOT do is put a list in front of anybody: the panel is not on screen in the first case,
 * and in the second the whole chat view is `inert` and `aria-hidden` behind the console. A section
 * nobody can see has not opened for them, which is what this guards the sentence below with.
 */
function onChat(state: OverlayState): boolean {
  return state.mode === "panel" && state.consoleTab === null;
}

/**
 * Open or shut the chat switcher, saying what the list holds when the reader has no other way to
 * hear it.
 *
 * `announce` is the door's answer and not this arm's, which is the rule the arriving-chat arms
 * already follow (`notice.ts`): `Ctrl+K` speaks, because the key names nothing and leaves the caret
 * where it was, and the header's chats button does not, because it carries `aria-expanded` and the
 * reader who pressed it is standing on it. Measured over thirteen doors before this: every one of
 * them left the caret exactly where it was and produced no live-region mutation at all, so the
 * button's own state was the whole of what a reader was handed.
 *
 * The notice is CARRIED rather than cleared on the silent paths, unlike the swap arms, which null
 * it. A toggle does not replace the panel's contents, so a sentence about the chat that arrived a
 * moment ago is still true; and the region reports mutations, so carrying the same notice object
 * says nothing twice.
 */
export function toggleSwitcher(state: OverlayState, announce: boolean): OverlayState {
  const open = !state.switcherOpen;
  const speaks = open && announce && onChat(state);
  const notice: Notice | null = speaks
    ? speak(state.notice, [switcherOpened(state.sessions.length)])
    : state.notice;
  return { ...state, switcherOpen: open, notice };
}

/** What the tab strip does, so it is idempotent: clicking the tab already showing leaves it
 *  showing. Switching tabs is a view change (`Panel` routes on the tab), so the panel morphs. */
export function openConsole(state: OverlayState, tab: ConsoleTab): OverlayState {
  return { ...state, consoleTab: tab };
}

/** What an OPENER does: the hint strip's sliders and its ?, and the ? key, each own one tab, so
 *  pressing the one you are already on closes the console and the other one switches. */
export function toggleConsole(state: OverlayState, tab: ConsoleTab): OverlayState {
  return { ...state, consoleTab: state.consoleTab === tab ? null : tab };
}

/** Esc and the header's chevron: out in one press, whichever tab is up. */
export function closeConsole(state: OverlayState): OverlayState {
  return { ...state, consoleTab: null };
}
