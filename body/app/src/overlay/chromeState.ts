import { type Notice, speak, switcherOpened } from "./notice";
import type { ConsoleTab, OverlayState } from "./overlayState";

/** Whether the chat is the view the reader is looking at. It reports what is on screen rather
 *  than what the state holds, so a key pressed off the chat opens rather than toggles. */
function onChat(state: OverlayState): boolean {
  return state.mode === "panel" && state.consoleTab === null;
}

/** Go to the chat, the way every other key aimed at it does. */
function ontoChat(state: OverlayState): OverlayState {
  return { ...state, mode: "panel", consoleTab: null, touched: true };
}

/** Open or shut the chat switcher, on the chat. Off the chat the press opens rather than toggles,
 *  because what the reader can see is a shut switcher either way. `announce` is decided by the
 *  caller: the key says what the list holds, and the header's button does not. */
export function toggleSwitcher(state: OverlayState, announce: boolean): OverlayState {
  const open = onChat(state) ? !state.switcherOpen : true;
  const notice: Notice | null =
    open && announce ? speak(state.notice, [switcherOpened(state.sessions.length)]) : state.notice;
  return { ...ontoChat(state), switcherOpen: open, notice };
}

/** What the tab strip does, so it is idempotent: clicking the tab already showing leaves it
 *  showing. */
export function openConsole(state: OverlayState, tab: ConsoleTab): OverlayState {
  return { ...state, consoleTab: tab };
}

/** What an opener does: the hint strip's sliders and its ?, and the ? key, each own one tab, so
 *  pressing the one you are already on closes the console and the other one switches. The key can
 *  be pressed off the chat, so "the one you are on" is asked of the screen, not of the state. */
export function toggleConsole(state: OverlayState, tab: ConsoleTab): OverlayState {
  const showing = state.mode === "panel" && state.consoleTab === tab;
  return { ...ontoChat(state), consoleTab: showing ? null : tab };
}

/** Esc and the header's chevron: out in one press, whichever tab is up. */
export function closeConsole(state: OverlayState): OverlayState {
  return { ...state, consoleTab: null };
}
