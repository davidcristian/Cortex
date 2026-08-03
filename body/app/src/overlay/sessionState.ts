import type { SessionMessage, SessionSummary } from "../bridge/types";
import type { OverlayState } from "./overlayState";
import type { Message } from "./turnState";

export const NEW_CHAT_TITLE = "New chat";
/**
 * The character bound on a title, the same number the brain's `cortex_core.sessions.TITLE_MAX`
 * bounds every listed title to, and tied to it by `scripts/crosscheck.py` so neither can move
 * alone.
 */
const TITLE_MAX = 48;

/** The live title for a chat the brain has not listed yet: the brain's rule, applied locally. */
export function deriveTitle(text: string): string {
  const oneLine = text.replace(/\s+/gu, " ").trim();
  return oneLine.length > TITLE_MAX ? `${oneLine.slice(0, TITLE_MAX)}…` : oneLine;
}

/** Stored history as overlay messages (nothing streams; ids restart per hydration). A reloaded
 *  reply carries no `thoughts`: reasoning is never persisted (ADR-0020), so its collapsed
 *  retrospective is a live-turn affordance only, gone once a chat is reloaded. */
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

/** The header title for a chat being loaded into the panel (ADR-0021 titles addendum). */
function headerTitle(
  sessions: readonly SessionSummary[],
  sessionId: string,
  messages: readonly SessionMessage[],
): string {
  const summary = sessions.find((s) => s.sessionId === sessionId);
  return summary ? summary.title : titleFor(messages);
}

/**
 * Load a stored chat into the panel: hydrate its messages, carry the switcher's title, and leave
 * the console the way `newChat` does (ADR-0035 addendum, 2026-08-03).
 */
export function openSession(
  state: OverlayState,
  sessionId: string,
  messages: readonly SessionMessage[],
): OverlayState {
  const loaded = hydrate(messages);
  return {
    ...state,
    mode: "panel",
    touched: true,
    sessionId,
    title: headerTitle(state.sessions, sessionId, messages),
    messages: loaded,
    switcherOpen: false,
    consoleTab: null,
    pendingConfirm: null,
    seq: loaded.length,
  };
}

/**
 * Adopt the most recent stored chat on cold start (ADR-0021 refinement): hydrate exactly like
 * `openSession` but preserve `mode` and the console tab, so a background restore never pops the
 * panel and never takes a view off it.
 */
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

/**
 * Remove a deleted chat from the switcher list, handling the current-session hazard (ADR-0021
 * delete addendum).
 */
export function deleteSession(
  state: OverlayState,
  sessionId: string,
  fallbackSessionId: string,
): OverlayState {
  const sessions = state.sessions.filter((s) => s.sessionId !== sessionId);
  if (sessionId !== state.sessionId) {
    return { ...state, sessions, touched: true };
  }
  return {
    ...state,
    sessions,
    touched: true,
    sessionId: fallbackSessionId,
    title: NEW_CHAT_TITLE,
    messages: [],
    pendingConfirm: null,
    seq: 0,
  };
}

/**
 * The session id to switch to when cycling from `currentId` by `delta` (-1 = newer / previous, +1
 * = older / next), or `null` for no move.
 */
export function cycleTarget(
  sessions: readonly SessionSummary[],
  currentId: string,
  delta: -1 | 1,
): string | null {
  const index = sessions.findIndex((s) => s.sessionId === currentId);
  // A current chat not in the list (index -1, a fresh unsaved chat) enters the list only
  // going older (delta 1 → index 0); an out-of-range target reads back as undefined → null.
  const target = index === -1 ? (delta === 1 ? 0 : -1) : index + delta;
  return sessions[target]?.sessionId ?? null;
}
