import type { TurnEvent } from "../bridge/types";
import { draftOf, dropDraft } from "./drafts";
import type { OverlayState } from "./overlayState";
import { NEW_CHAT_TITLE, deriveTitle } from "./sessionState";

// The turn half of the overlay state (ADR-0011, design/overlay-ux.md §4): what a message is, and
// how one `Converse` turn's events fold into the transcript. Split from `overlayState.ts` (which
// re-exports the pieces components use) the way `sessionState.ts` already split off the
// chat-switching half, to keep every one of them under the repo line cap. Only types cross back,
// so the runtime import graph stays one-directional: `overlayState` imports these, never the
// reverse.

/**
 * The brain-side name of the screen-capture built-in (ADR-0029). Matched by name rather than by
 * a new event field: the tool activity the brain already streams carries it, and a second seam
 * field would be one more place the two ends could disagree about the same fact.
 */
export const CAPTURE_SCREEN_TOOL = "capture_screen";

/**
 * How far this turn's screen-capture claim has climbed (ADR-0029 outcome addendum). Two rungs,
 * weakest first, and the only two the brain can prove: `"asked"` is what the
 * pre-dispatch activity proves, `"read"` what the post-dispatch outcome proves. `null` is a turn
 * that asked for nothing.
 *
 * The ladder only ever climbs within a turn. Over-reporting a capture is the safe direction
 * for a privacy indicator and under-reporting is the dangerous one, so no event may weaken a
 * claim: a failed capture is indistinguishable from one that failed *after* the shutter fired,
 * where the pixels really did leave the display and the body really did show its own receipt.
 * Only `endTurn` resets, because the turn that looked is over.
 */
export type CaptureClaim = "asked" | "read";

export interface Message {
  readonly id: string;
  readonly role: "user" | "assistant";
  readonly content: string;
  readonly streaming: boolean;
  readonly tool: string | null;
  readonly status: string | null;
  /** The status event's `state` (e.g. "thinking"), so the chip can treat deliberation
   *  distinctly from a generic status; null until a status event lands (ADR-0020). */
  readonly statusState: string | null;
  /** The reply's accumulated reasoning trace: every `"thinking"` status's detail, concatenated
   *  in order (each already guardrail-scrubbed brain-side, ADR-0020 addendum). `status` shows only
   *  the latest delta and drops when the turn settles; `thoughts` retains the whole trace so the
   *  settled reply offers a collapsed retrospective. In-memory only, never persisted, so a reloaded
   *  chat carries `""` (reasoning persistence stays declined). Empty until deliberation streams. */
  readonly thoughts: string;
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
 *  or a turn already running is a no-op, so a double-send cannot open a second stream (and a blank
 *  one leaves the field exactly as it is, nothing having been sent out of it).
 *
 *  Sending a text empties the field that held it, which is asked of the text rather than of the
 *  control it was sent from (`drafts.ts`). The composer sends its own draft, so the draft goes; an
 *  example chip on the empty state sends the chip's words, so a half-typed question sitting in the
 *  field beside it is not thrown away by a button the user pressed for something else. */
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
      // The chip is emitted just before the dispatch, so it proves the assistant asked to look
      // and no more; the `toolOutcome` below is what can raise that to "read". `?? "asked"` is
      // what keeps the rung from falling: a second capture asked for after a first one was read
      // leaves the claim at "read".
      const capture =
        event.toolName === CAPTURE_SCREEN_TOOL ? (state.capture ?? "asked") : state.capture;
      const chipped = patchStreaming(state, (m) => ({
        ...m,
        tool: `${event.toolName}: ${event.summary}`,
      }));
      return { ...chipped, capture };
    }
    case "toolOutcome":
      // How the announced dispatch ended (ADR-0029 outcome addendum). It may only ever
      // strengthen the claim: `ok` false means the brain cannot say the screen was read, never
      // that it was not read, so it changes nothing and the dot stays where the ask put it. A
      // true one is the only evidence that promotes the claim, and it promotes even a claim this
      // side never saw asked (a dropped activity must not cost the stronger, truer statement).
      return event.toolName === CAPTURE_SCREEN_TOOL && event.ok
        ? { ...state, capture: "read" }
        : state;
    case "status": {
      // A "thinking" status is one reasoning-trace delta (ADR-0020), already guardrail-scrubbed
      // brain-side, so accumulate it into `thoughts` for the settled reply's collapsed
      // retrospective while `status`/`statusState` still drive the live chip. Any other status (a
      // future swap/queue state) drives the chip only and never joins the reasoning trace.
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
      // The brain stopped waiting (timeout, or its input ended), so the question on screen
      // can no longer be answered: close it rather than let a click land on nothing
      // (ADR-0022). Only the card actually showing goes; a resolution for anything else is
      // late or unknown and changes nothing, the same stale-id rule the answer path has.
      return state.pendingConfirm?.confirmId === event.confirmId
        ? { ...state, pendingConfirm: null }
        : state;
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
export function endTurn(state: OverlayState, error: string | null): OverlayState {
  const ended = patchStreaming(state, (m) => ({ ...m, streaming: false, error }));
  return {
    ...ended,
    mode: state.mode === "orb" ? "preview" : state.mode,
    pendingConfirm: null,
    // The turn is over, so the picture it took is out of context: the indicator goes out with
    // it rather than persisting into a turn that never looked at anything. The one place the
    // claim ladder is allowed to fall, and it falls all the way rather than a rung.
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
