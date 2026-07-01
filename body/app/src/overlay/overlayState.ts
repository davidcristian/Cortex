import type { TransportError, TurnEvent } from "../bridge/types";

// The overlay's pure state + reducer (ADR-0011, design/overlay-ux.md §4). Kept out of React so
// the interaction model (folding a Converse turn's events into messages, and the
// dismiss-while-streaming → orb → preview mode machine) is exhaustively testable. Components
// dispatch actions and render the result; animation lives in CSS.

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

export interface OverlayState {
  readonly mode: Mode;
  readonly title: string;
  readonly messages: readonly Message[];
  readonly seq: number;
}

export type Action =
  | { readonly kind: "open" }
  | { readonly kind: "submit"; readonly text: string }
  | { readonly kind: "event"; readonly event: TurnEvent }
  | { readonly kind: "transportError"; readonly error: TransportError }
  | { readonly kind: "dismiss" }
  | { readonly kind: "previewFade" }
  | { readonly kind: "newChat" };

const NEW_CHAT_TITLE = "New chat";
const TITLE_MAX = 32;

export const initialState: OverlayState = {
  mode: "hidden",
  title: NEW_CHAT_TITLE,
  messages: [],
  seq: 0,
};

/** True while an assistant message is still streaming. */
export function isTurnActive(state: OverlayState): boolean {
  return state.messages.some((message) => message.streaming);
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
      return { ...state, mode: isTurnActive(state) ? "orb" : "hidden" };
    case "previewFade":
      return state.mode === "preview" ? { ...state, mode: "hidden" } : state;
    case "newChat":
      return { ...state, mode: "panel", title: NEW_CHAT_TITLE, messages: [] };
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
    case "complete":
      return endTurn(state, null);
    case "failed":
      return endTurn(state, `${event.code}: ${event.message}`);
  }
}

/** End the streaming turn (optionally with an error) and surface it: orb → preview. */
function endTurn(state: OverlayState, error: string | null): OverlayState {
  const ended = patchStreaming(state, (m) => ({ ...m, streaming: false, error }));
  return { ...ended, mode: state.mode === "orb" ? "preview" : state.mode };
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

function deriveTitle(text: string): string {
  const oneLine = text.replace(/\s+/gu, " ").trim();
  return oneLine.length > TITLE_MAX ? `${oneLine.slice(0, TITLE_MAX)}…` : oneLine;
}
