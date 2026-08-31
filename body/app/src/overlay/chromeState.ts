import { type Notice, speak, switcherOpened } from "./notice";
import type { ConsoleTab, OverlayState } from "./overlayState";

// Which of the panel's sections is showing.
//
// The switcher's list and the console's tabs are the two things the panel puts up around the chat
// without changing which conversation is in it, so they are one responsibility and it is not the
// conversation's. Split out of `overlayState.ts` when the switcher grew the rule below, the third
// such split beside the session switching and the turn fold, and for the same reason: the line cap
// keeps each of them explainable in one file.

/**
 * Whether the chat is the view the reader is looking at.
 *
 * The overlay's global keys stay live while it is not, which is right for the ones that summon:
 * `Ctrl+N` and the cycle keys set `mode: "panel"` and drop the console on their way through, so a
 * key aimed at the conversation lands in the conversation (`sessionState.ts` argues that pair).
 * The two keys aimed at the panel's other surfaces reach the same rule through this predicate. It
 * reports what is on screen rather than what the store holds: off the chat, a shut switcher and a
 * shut console are what the reader sees whatever the flags say, so the press opens rather than
 * toggling.
 */
function onChat(state: OverlayState): boolean {
  return state.mode === "panel" && state.consoleTab === null;
}

/** Land on the chat, the way every other key aimed at it does. `touched` goes with the summon for
 *  the reason the summon sets it: a cold-start adoption must not replace what a key just put up
 *  (`sessionState.adopt`). */
function ontoChat(state: OverlayState): OverlayState {
  return { ...state, mode: "panel", consoleTab: null, touched: true };
}

/**
 * Open or shut the chat switcher, on the chat, saying what the list holds when the reader has no
 * other way to hear it.
 *
 * `Ctrl+K` used to flip the flag wherever it was pressed, so from a tucked panel and from behind an
 * open console it mounted the rows and turned `aria-expanded` true where nobody could see either,
 * and the next summon found a list open that nobody had opened. It lands on the chat instead, which
 * is the answer the two swap keys already give from the same two places, and off the chat the press
 * opens rather than toggles: what a reader can see is a shut switcher, so toggling would let one
 * press close a list they were never shown.
 *
 * `announce` is settled by the caller and not by this arm, the rule the arriving-chat arms already
 * follow (`notice.ts`): `Ctrl+K` speaks, because the key names nothing and leaves the caret where
 * it was, and the header's chats button does not, because it carries `aria-expanded` and the reader
 * who pressed it is standing on it. Measured over the thirteen openers that existed before this:
 * every one left the caret exactly where it was and produced no live-region mutation at all, so the
 * button's own state was the whole of what a reader was handed. No caller can make that sentence
 * false now, the list being on screen whenever this arm opens it.
 *
 * The notice is carried rather than cleared on the silent paths, unlike the swap arms, which null
 * it. A toggle does not replace the panel's contents, so a sentence about the chat that arrived a
 * moment ago is still true; and the region reports mutations, so carrying the same notice object
 * says nothing twice.
 */
export function toggleSwitcher(state: OverlayState, announce: boolean): OverlayState {
  const open = onChat(state) ? !state.switcherOpen : true;
  const notice: Notice | null =
    open && announce ? speak(state.notice, [switcherOpened(state.sessions.length)]) : state.notice;
  return { ...ontoChat(state), switcherOpen: open, notice };
}

/** What the tab strip does, so it is idempotent: clicking the tab already showing leaves it
 *  showing. Switching tabs is a view change (`Panel` routes on the tab), so the panel morphs. No
 *  off-screen caller has to be answered for here: every control that dispatches it lives inside
 *  the console, which is on screen for as long as they are. */
export function openConsole(state: OverlayState, tab: ConsoleTab): OverlayState {
  return { ...state, consoleTab: tab };
}

/** What an opener does: the hint strip's sliders and its ?, and the ? key, each own one tab, so
 *  pressing the one you are already on closes the console and the other one switches. The two
 *  buttons are on the chat whenever they can be pressed at all; the key is not, so "the one you are
 *  already on" is asked of the screen and not of the flag, and `?` from a tucked panel puts the
 *  shortcuts up rather than mounting them behind a window that is not there. */
export function toggleConsole(state: OverlayState, tab: ConsoleTab): OverlayState {
  const showing = state.mode === "panel" && state.consoleTab === tab;
  return { ...ontoChat(state), consoleTab: showing ? null : tab };
}

/** Esc and the header's chevron: out in one press, whichever tab is up. */
export function closeConsole(state: OverlayState): OverlayState {
  return { ...state, consoleTab: null };
}
