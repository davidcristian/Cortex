// The turn half of the overlay state: what a message is, and how one turn's events fold into the
// transcript. `overlayState.ts` re-exports the pieces components use, and only types cross back.

import type { TurnEvent } from "../bridge/types";
import { draftOf, dropDraft } from "./drafts";
import type { OverlayState } from "./overlayState";
import { NEW_CHAT_TITLE, deriveTitle } from "./sessionState";

/** The brain-side name of the screen-capture built-in. Matched by name rather than by a new event
 *  field, because the tool activity the brain already streams contains it. */
export const CAPTURE_SCREEN_TOOL = "capture_screen";

/** How far this turn's screen-capture claim has climbed: `asked` is what the pre-dispatch activity
 *  proves, `read` what the outcome proves, and `null` is a turn that asked for nothing. It only
 *  ever climbs within a turn, because over-reporting is the safe direction here. */
export type CaptureClaim = "asked" | "read";

export interface Message {
  readonly id: string;
  readonly role: "user" | "assistant";
  readonly content: string;
  readonly streaming: boolean;
  readonly tool: string | null;
  readonly status: string | null;
  /** The status event's `state`, such as "thinking", so the chip can show deliberation
   *  differently from a generic status. Null until a status event arrives. */
  readonly statusState: string | null;
  /** The reply's reasoning trace: every `"thinking"` status's detail in order, each already
   *  filtered brain-side. `status` shows only the latest delta and clears when the turn settles.
   *  In memory only, so a reloaded chat has `""`. */
  readonly thoughts: string;
  readonly error: string | null;
}

/** A tool call waiting for the user's mid-turn approval; at most one per turn. */
export interface PendingConfirm {
  readonly confirmId: string;
  readonly toolName: string;
  /** The exact draft being approved, one JSON object string (the executed contract). */
  readonly argumentsJson: string;
  readonly reason: string;
}

/** True while an assistant message is still streaming. */
export function isTurnActive(state: OverlayState): boolean {
  return state.messages.some((message) => message.streaming);
}

/** The most recent assistant reply's text (for the minimized preview); "" if none yet. */
export function latestReply(state: OverlayState): string {
  const reply = [...state.messages].reverse().find((message) => message.role === "assistant");
  return reply?.content ?? "";
}

/** Start a turn: the user's line plus the empty assistant bubble the stream fills. A blank draft
 *  or a turn already running is a no-op. Sending empties the field that held the text, which is
 *  asked of the text rather than of the control it was sent from. */
export function submit(state: OverlayState, text: string): OverlayState {
  const trimmed = text.trim();
  if (isTurnActive(state) || trimmed.length === 0) {
    return state;
  }
  const user: Message = message(`m${state.seq}`, "user", trimmed, false);
  const assistant: Message = message(`m${state.seq + 1}`, "assistant", "", true);
  const title = state.title === NEW_CHAT_TITLE ? deriveTitle(trimmed) : state.title;
  const sentTheDraft = draftOf(state.drafts, state.sessionId) === text;
  return {
    ...state,
    mode: "panel",
    touched: true,
    title,
    drafts: sentTheDraft ? dropDraft(state.drafts, state.sessionId) : state.drafts,
    messages: [...state.messages, user, assistant],
    seq: state.seq + 2,
  };
}

/** Fold one streamed turn event into the state. */
export function applyEvent(state: OverlayState, event: TurnEvent): OverlayState {
  switch (event.kind) {
    case "delta":
      return patchStreaming(state, (m) => ({ ...m, content: m.content + event.text }));
    case "toolActivity": {
      // The chip is emitted just before the dispatch, so it proves the assistant asked to look and
      // no more. `?? "asked"` keeps the claim from falling: a second capture asked for after a
      // first was read leaves it at "read".
      const capture =
        event.toolName === CAPTURE_SCREEN_TOOL ? (state.capture ?? "asked") : state.capture;
      const chipped = patchStreaming(state, (m) => ({
        ...m,
        tool: `${event.toolName}: ${event.summary}`,
      }));
      return { ...chipped, capture };
    }
    case "toolOutcome":
      // It may only ever strengthen the claim: `ok` false means the brain cannot say the screen was
      // read, never that it was not, so it changes nothing. A true one promotes even a claim this
      // side never saw asked, because a dropped activity must not cost the truer statement.
      return event.toolName === CAPTURE_SCREEN_TOOL && event.ok
        ? { ...state, capture: "read" }
        : state;
    case "status": {
      // A "thinking" status is one reasoning delta, already filtered brain-side, so it joins
      // `thoughts` as well as the live chip. Any other status drives the chip only.
      const thinking = event.state === "thinking";
      return patchStreaming(state, (m) => ({
        ...m,
        status: event.detail,
        statusState: event.state,
        thoughts: thinking ? m.thoughts + event.detail : m.thoughts,
      }));
    }
    case "confirmRequest":
      return applyConfirmRequest(state, event);
    case "confirmResolved":
      // The brain stopped waiting, so the question on screen can no longer be answered: close it
      // rather than let a click reach nothing. Only the card showing goes.
      return state.pendingConfirm?.confirmId === event.confirmId
        ? { ...state, pendingConfirm: null }
        : state;
    case "complete":
      return endTurn(state, null);
    case "failed":
      return endTurn(state, `${event.code}: ${event.message}`);
  }
}

/** A call is waiting for approval: raise the card, showing it as a completed turn does (orb then
 *  preview). Only a live turn can ask, so a cancelled turn's late request revives nothing. */
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

/** End the streaming turn, with an error or without, and show it: orb then preview. Any pending
 *  approval dies with its turn, the stream being gone and that being the deny. */
export function endTurn(state: OverlayState, error: string | null): OverlayState {
  const ended = patchStreaming(state, (m) => ({ ...m, streaming: false, error }));
  return {
    ...ended,
    mode: state.mode === "orb" ? "preview" : state.mode,
    pendingConfirm: null,
    // The turn is over, so the picture it took is out of context and the indicator goes out with
    // it. The one place the claim is allowed to fall, and it falls all the way.
    capture: null,
  };
}

function patchStreaming(state: OverlayState, patch: (m: Message) => Message): OverlayState {
  return {
    ...state,
    messages: state.messages.map((m) => (m.streaming ? patch(m) : m)),
  };
}

function message(id: string, role: Message["role"], content: string, streaming: boolean): Message {
  const base = { id, role, content, streaming, tool: null, status: null };
  return { ...base, statusState: null, thoughts: "", error: null };
}
