import type { SessionMessage, SessionSummary } from "../bridge/types";
import { dropDraft } from "./drafts";
import { arrived, chatDeleted, speak } from "./notice";
import type { OverlayState } from "./overlayState";
import type { Message } from "./turnState";

// The session-switching half of the overlay state: starting a fresh chat, loading a stored one,
// adopting the most recent on cold start, cycling between recent chats, and the title rule they
// share. `overlayState.ts` re-exports the pieces components use, and only types cross back.

export const NEW_CHAT_TITLE = "New chat";
/** The character bound on a title, the same number the brain's `cortex_core.sessions.TITLE_MAX`
 *  uses, and tied to it by `scripts/crosscheck.py` so neither can move alone. It must be the same
 *  number, because `deriveTitle` stands in for the brain's rule until the chat is listed. */
const TITLE_MAX = 48;

/** The live title for a chat the brain has not listed yet: the brain's rule, applied locally.
 *  Collapse runs of whitespace to single spaces, then past `TITLE_MAX` characters cut and add one
 *  ellipsis. Once the chat is listed, the brain's own title replaces this one. */
export function deriveTitle(text: string): string {
  const oneLine = text.replace(/\s+/gu, " ").trim();
  return oneLine.length > TITLE_MAX ? `${oneLine.slice(0, TITLE_MAX)}…` : oneLine;
}

/** Stored history as overlay messages (nothing streams; ids restart per hydration). A reloaded
 *  reply has no `thoughts`, because reasoning is never persisted. */
function hydrate(messages: readonly SessionMessage[]): Message[] {
  return messages.map((m, index) => ({
    id: `m${index}`,
    role: m.role,
    content: m.text,
    streaming: false,
    tool: null,
    status: null,
    statusState: null,
    thoughts: "",
    error: null,
  }));
}

/** The header title a stored history derives: its first user message, else a fresh-chat one. */
function titleFor(messages: readonly SessionMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  return firstUser ? deriveTitle(firstUser.text) : NEW_CHAT_TITLE;
}

/** The header title for a chat being loaded into the panel. Taken from the switcher's own summary
 *  when the chat is in the loaded list, so the header and the row cannot differ; a chat outside
 *  that list falls back to the local first-message rule. */
function headerTitle(
  sessions: readonly SessionSummary[],
  sessionId: string,
  messages: readonly SessionMessage[],
): string {
  const summary = sessions.find((s) => s.sessionId === sessionId);
  return summary ? summary.title : titleFor(messages);
}

/** Start a fresh chat over whatever is on screen. The console leaves with the old chat, because
 *  both gestures here are aimed at the conversation. The fresh id has no draft parked under it, so
 *  the sentence the user was half way through stays with the chat it was typed into. */
export function newChat(state: OverlayState, sessionId: string, announce: boolean): OverlayState {
  return {
    ...state,
    mode: "panel",
    touched: true,
    sessionId,
    title: NEW_CHAT_TITLE,
    notice: announce ? speak(state.notice, [arrived(NEW_CHAT_TITLE)]) : null,
    arrival: state.arrival + 1,
    messages: [],
    switcherOpen: false,
    consoleTab: null,
    pendingConfirm: null,
  };
}

/** Load a stored chat into the panel: hydrate its messages, take the switcher's title, and leave
 *  the console the way `newChat` does. `announce` is the caller's decision, because a cycle key and
 *  a reminder's open control speak and a switcher row does not. */
export function openSession(
  state: OverlayState,
  sessionId: string,
  messages: readonly SessionMessage[],
  announce: boolean,
): OverlayState {
  const loaded = hydrate(messages);
  const title = headerTitle(state.sessions, sessionId, messages);
  return {
    ...state,
    mode: "panel",
    touched: true,
    sessionId,
    title,
    notice: announce ? speak(state.notice, [arrived(title)]) : null,
    arrival: state.arrival + 1,
    messages: loaded,
    switcherOpen: false,
    consoleTab: null,
    pendingConfirm: null,
    seq: loaded.length,
  };
}

/** Adopt the most recent stored chat on cold start: hydrate as `openSession` does but keep `mode`
 *  and the console tab, so a background restore never opens the panel. It runs only while
 *  `touched` is false, so a racing summon, submit, cycle or new chat wins. */
export function adoptSession(
  state: OverlayState,
  sessionId: string,
  messages: readonly SessionMessage[],
): OverlayState {
  if (state.touched) {
    return state;
  }
  const loaded = hydrate(messages);
  return {
    ...state,
    sessionId,
    title: headerTitle(state.sessions, sessionId, messages),
    messages: loaded,
    seq: loaded.length,
  };
}

/** Remove a deleted chat from the switcher list. Deleting any other chat drops its row; deleting
 *  the open one resets the panel to a fresh empty chat in place, taking `fallbackSessionId` for
 *  its identity because the reducer cannot make ids. Both paths drop the chat's draft. */
export function deleteSession(
  state: OverlayState,
  sessionId: string,
  fallbackSessionId: string,
): OverlayState {
  const sessions = state.sessions.filter((s) => s.sessionId !== sessionId);
  const drafts = dropDraft(state.drafts, sessionId);
  const gone = sessions.length < state.sessions.length ? [chatDeleted(sessions.length)] : [];
  if (sessionId !== state.sessionId) {
    return {
      ...state,
      sessions,
      drafts,
      touched: true,
      notice: gone.length === 0 ? state.notice : speak(state.notice, gone),
    };
  }
  return {
    ...state,
    sessions,
    drafts,
    touched: true,
    sessionId: fallbackSessionId,
    title: NEW_CHAT_TITLE,
    notice: speak(state.notice, [...gone, arrived(NEW_CHAT_TITLE)]),
    arrival: state.arrival + 1,
    messages: [],
    pendingConfirm: null,
    seq: 0,
  };
}

/** The session id to switch to when cycling from `currentId` by `delta` (-1 = newer, +1 = older),
 *  or `null` for no move. `sessions` is newest-first, and a current chat that is not in the list,
 *  which is a fresh unsaved one, enters it only on `+1`. */
export function cycleTarget(
  sessions: readonly SessionSummary[],
  currentId: string,
  delta: -1 | 1,
): string | null {
  const index = sessions.findIndex((s) => s.sessionId === currentId);
  // An out-of-range target reads back as undefined, which becomes null.
  const target = index === -1 ? (delta === 1 ? 0 : -1) : index + delta;
  return sessions[target]?.sessionId ?? null;
}
