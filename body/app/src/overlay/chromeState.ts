import { type Notice, speak, switcherOpened } from "./notice";
import type { ConsoleTab, OverlayState } from "./overlayState";

/** Whether the chat is the view a reader is actually looking at. */
function onChat(state: OverlayState): boolean {
  return state.mode === "panel" && state.consoleTab === null;
}

/**
 * Open or shut the chat switcher, saying what the list holds when the reader has no other way to
 * hear it.
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
