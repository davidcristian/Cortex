import { type Notice, speak, switcherOpened } from "./notice";
import type { ConsoleTab, OverlayState } from "./overlayState";

/** Whether the chat is the view a reader is actually looking at. */
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
 */
export function toggleSwitcher(state: OverlayState, announce: boolean): OverlayState {
  const open = onChat(state) ? !state.switcherOpen : true;
  const notice: Notice | null =
    open && announce ? speak(state.notice, [switcherOpened(state.sessions.length)]) : state.notice;
  return { ...ontoChat(state), switcherOpen: open, notice };
}

/**
 * What the tab strip does, so it is idempotent: clicking the tab already showing leaves it
 * showing.
 */
export function openConsole(state: OverlayState, tab: ConsoleTab): OverlayState {
  return { ...state, consoleTab: tab };
}

/** What an OPENER does: the hint strip's sliders and its ?, and the ? */
export function toggleConsole(state: OverlayState, tab: ConsoleTab): OverlayState {
  const showing = state.mode === "panel" && state.consoleTab === tab;
  return { ...ontoChat(state), consoleTab: showing ? null : tab };
}

/** Esc and the header's chevron: out in one press, whichever tab is up. */
export function closeConsole(state: OverlayState): OverlayState {
  return { ...state, consoleTab: null };
}
