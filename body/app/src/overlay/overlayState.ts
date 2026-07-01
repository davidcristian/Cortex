import type { TransportError, TurnEvent } from "../bridge/types";

// The overlay's display state and the pure reducer that folds a Converse turn's
// events into it. Kept separate from React so it is exhaustively testable. It is the
// heart of "prompt → stream → render" (ADR-0011).

export type OverlayPhase = "idle" | "streaming" | "complete" | "failed" | "error";

export interface OverlayState {
  readonly phase: OverlayPhase;
  readonly reply: string;
  readonly status: string | null;
  readonly toolActivity: string | null;
  readonly error: string | null;
  readonly turnId: string | null;
}

export const initialState: OverlayState = {
  phase: "idle",
  reply: "",
  status: null,
  toolActivity: null,
  error: null,
  turnId: null,
};

/** Begin a fresh turn. Clears the previous reply and marks streaming. */
export function startTurn(): OverlayState {
  return { ...initialState, phase: "streaming" };
}

/** Fold one brain event into the overlay's display state. */
export function reduceEvent(state: OverlayState, event: TurnEvent): OverlayState {
  switch (event.kind) {
    case "delta":
      return { ...state, reply: state.reply + event.text };
    case "toolActivity":
      return { ...state, toolActivity: `${event.toolName}: ${event.summary}` };
    case "status":
      return { ...state, status: event.detail };
    case "complete":
      return { ...state, phase: "complete", turnId: event.turnId };
    case "failed":
      return { ...state, phase: "failed", error: `${event.code}: ${event.message}` };
  }
}

/** A transport failure (unreachable brain, bad stream) ends the turn in error. */
export function reduceError(state: OverlayState, error: TransportError): OverlayState {
  return { ...state, phase: "error", error: error.message };
}

/** Whether a turn is streaming. The overlay disables input while it is. */
export function isBusy(state: OverlayState): boolean {
  return state.phase === "streaming";
}
