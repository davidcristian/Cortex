import type { SessionMessage, SessionSummary, TransportError, TurnEvent } from "../bridge/types";
import { NEW_CHAT_TITLE, adoptSession, deriveTitle, openSession } from "./sessionState";

// The overlay's pure state + reducer (ADR-0011, design/overlay-ux.md §4). Kept out of React so
// the interaction model (folding a Converse turn's events into messages, and the
// dismiss-while-streaming → orb → preview mode machine) is exhaustively testable. Components
// dispatch actions and render the result; animation lives in CSS. The session-switching
// helpers live in `sessionState.ts` (re-exported below), keeping both files under the line cap.

export { cycleTarget } from "./sessionState";

/** Where the overlay is on screen. */
export type Mode = "hidden" | "panel" | "orb" | "preview";

export interface Message {
  readonly id: string;
  readonly role: "user" | "assistant";
  readonly content: string;
  readonly streaming: boolean;
  readonly tool: string | null;
  readonly status: string | null;
  readonly error: string | null;
}

/** A gated tool call awaiting the user's mid-turn approval (ADR-0022); at most one per turn. */
export interface PendingConfirm {
  readonly confirmId: string;
  readonly toolName: string;
  /** The exact draft being approved, one JSON object string (the executed contract). */
  readonly argumentsJson: string;
  readonly reason: string;
}

export interface OverlayState {
  readonly mode: Mode;
  /** The current chat's session id (its identity for `converse`, history, and cycling). */
  readonly sessionId: string;
  readonly title: string;
  readonly messages: readonly Message[];
  /** Recent chats for the switcher / cycling (store-backed, newest-active first). */
  readonly sessions: readonly SessionSummary[];
  /** Whether the switcher list is open in the header. */
  readonly switcherOpen: boolean;
  /** Whether the full shortcut sheet covers the panel (design/overlay-ux.md §6). */
  readonly sheetOpen: boolean;
  /** The approval the current turn is paused on, if any (ADR-0022). */
  readonly pendingConfirm: PendingConfirm | null;
  readonly seq: number;
}

export type Action =
  | { readonly kind: "open" }
  | { readonly kind: "submit"; readonly text: string }
  | { readonly kind: "event"; readonly event: TurnEvent }
  | { readonly kind: "transportError"; readonly error: TransportError }
  | { readonly kind: "dismiss" }
  | { readonly kind: "stop" }
  | { readonly kind: "confirmResolved"; readonly approved: boolean }
  | { readonly kind: "previewFade" }
  | { readonly kind: "newChat"; readonly sessionId: string }
  | { readonly kind: "sessionsLoaded"; readonly sessions: readonly SessionSummary[] }
  | {
      readonly kind: "openSession";
      readonly sessionId: string;
      readonly messages: readonly SessionMessage[];
    }
  | {
      readonly kind: "adoptSession";
      readonly sessionId: string;
      readonly messages: readonly SessionMessage[];
    }
  | { readonly kind: "toggleSwitcher" }
  | { readonly kind: "toggleSheet" };

/** A fresh, empty overlay state for `sessionId` (a new chat). */
export function createInitialState(sessionId: string): OverlayState {
  return {
    mode: "hidden",
    sessionId,
    title: NEW_CHAT_TITLE,
    messages: [],
    sessions: [],
    switcherOpen: false,
    sheetOpen: false,
    pendingConfirm: null,
    seq: 0,
  };
}

export const initialState: OverlayState = createInitialState("");

/** True while an assistant message is still streaming. */
export function isTurnActive(state: OverlayState): boolean {
  return state.messages.some((message) => message.streaming);
}

/** The most recent assistant reply's text (for the minimized preview); "" if none yet. */
export function latestReply(state: OverlayState): string {
  const reply = [...state.messages].reverse().find((message) => message.role === "assistant");
  return reply?.content ?? "";
}

export function reduce(state: OverlayState, action: Action): OverlayState {
  switch (action.kind) {
    case "open":
      return { ...state, mode: "panel" };
    case "submit":
      return submit(state, action.text);
    case "event":
      return applyEvent(state, action.event);
    case "transportError":
      return endTurn(state, action.error.message);
    case "dismiss":
      // Dismissing drops any pending approval with it (walking away is a deny, since the brain
      // fails closed by timeout, ADR-0022); the turn itself keeps streaming to the store. The
      // shortcut sheet closes too, so a re-summoned panel never opens onto stale help.
      return {
        ...state,
        mode: isTurnActive(state) ? "orb" : "hidden",
        sheetOpen: false,
        pendingConfirm: null,
      };
    case "stop":
      // User cancelled the turn: end the streaming reply in place (keep the partial text,
      // no error) and stay in the panel. This differs from dismiss, which minimizes to the orb.
      return endTurn(state, null);
    case "confirmResolved":
      // The user answered (either way); the card leaves. The answer itself rides the bridge.
      return { ...state, pendingConfirm: null };
    case "previewFade":
      // A pending approval waits to be seen (the errors rule, design/overlay-ux.md §4), and a
      // still-streaming turn is never faded from under: a confirm approved mid-turn keeps the
      // preview up until the turn completes, then the fade countdown starts (useOverlay).
      return state.mode === "preview" && state.pendingConfirm === null && !isTurnActive(state)
        ? { ...state, mode: "hidden" }
        : state;
    case "newChat":
      return {
        ...state,
        mode: "panel",
        sessionId: action.sessionId,
        title: NEW_CHAT_TITLE,
        messages: [],
        switcherOpen: false,
        pendingConfirm: null,
      };
    case "sessionsLoaded":
      return { ...state, sessions: action.sessions };
    case "openSession":
      return openSession(state, action.sessionId, action.messages);
    case "adoptSession":
      return adoptSession(state, action.sessionId, action.messages);
    case "toggleSwitcher":
      return { ...state, switcherOpen: !state.switcherOpen };
    case "toggleSheet":
      return { ...state, sheetOpen: !state.sheetOpen };
  }
}

function submit(state: OverlayState, text: string): OverlayState {
  const trimmed = text.trim();
  if (isTurnActive(state) || trimmed.length === 0) {
    return state;
  }
  const user: Message = message(`m${state.seq}`, "user", trimmed, false);
  const assistant: Message = message(`m${state.seq + 1}`, "assistant", "", true);
  const title = state.title === NEW_CHAT_TITLE ? deriveTitle(trimmed) : state.title;
  return {
    ...state,
    mode: "panel",
    title,
    messages: [...state.messages, user, assistant],
    seq: state.seq + 2,
  };
}

function applyEvent(state: OverlayState, event: TurnEvent): OverlayState {
  switch (event.kind) {
    case "delta":
      return patchStreaming(state, (m) => ({ ...m, content: m.content + event.text }));
    case "toolActivity":
      return patchStreaming(state, (m) => ({ ...m, tool: `${event.toolName}: ${event.summary}` }));
    case "status":
      return patchStreaming(state, (m) => ({ ...m, status: event.detail }));
    case "confirmRequest":
      return applyConfirmRequest(state, event);
    case "complete":
      return endTurn(state, null);
    case "failed":
      return endTurn(state, `${event.code}: ${event.message}`);
  }
}

/** A gated call awaits approval: raise the card, surfacing it like a completed turn (orb →
 *  preview). Only a live turn can ask. A cancelled/dead turn's late request must not resurrect
 *  UI state (the same no-op property `patchStreaming` gives every other event). */
function applyConfirmRequest(
  state: OverlayState,
  event: Extract<TurnEvent, { kind: "confirmRequest" }>,
): OverlayState {
  if (!isTurnActive(state)) {
    return state;
  }
  return {
    ...state,
    mode: state.mode === "orb" ? "preview" : state.mode,
    pendingConfirm: {
      confirmId: event.confirmId,
      toolName: event.toolName,
      argumentsJson: event.argumentsJson,
      reason: event.reason,
    },
  };
}

/** End the streaming turn (optionally with an error) and surface it: orb → preview. Any pending
 *  approval dies with its turn. The stream is gone, and stream-death is the deny (ADR-0022). */
function endTurn(state: OverlayState, error: string | null): OverlayState {
  const ended = patchStreaming(state, (m) => ({ ...m, streaming: false, error }));
  return { ...ended, mode: state.mode === "orb" ? "preview" : state.mode, pendingConfirm: null };
}

function patchStreaming(state: OverlayState, patch: (m: Message) => Message): OverlayState {
  return {
    ...state,
    messages: state.messages.map((m) => (m.streaming ? patch(m) : m)),
  };
}

function message(id: string, role: Message["role"], content: string, streaming: boolean): Message {
  return { id, role, content, streaming, tool: null, status: null, error: null };
}
