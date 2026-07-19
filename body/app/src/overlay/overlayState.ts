import type {
  DueReminder,
  LinkStatus,
  SessionMessage,
  SessionSummary,
  TransportError,
  TurnEvent,
} from "../bridge/types";
import {
  INITIAL_LINK,
  type LinkView,
  linkFailed,
  linkObserved,
  linkProbeEnded,
  linkProbing,
  linkServing,
} from "./linkState";
import {
  NEW_CHAT_TITLE,
  adoptSession,
  deleteSession,
  deriveTitle,
  openSession,
} from "./sessionState";

// The overlay's pure state + reducer (ADR-0011, design/overlay-ux.md §4). Kept out of React so
// the interaction model (folding a Converse turn's events into messages, and the
// dismiss-while-streaming → orb → preview mode machine) is exhaustively testable. Components
// dispatch actions and render the result; animation lives in CSS. The session-switching
// helpers live in `sessionState.ts` (re-exported below), keeping both files under the line cap.

export { cycleTarget } from "./sessionState";

/**
 * The brain-side name of the screen-capture built-in (ADR-0029). Matched by name rather than by
 * a new event field: the tool activity the brain already streams carries it, and a second seam
 * field would be one more place the two ends could disagree about the same fact.
 */
export const CAPTURE_SCREEN_TOOL = "capture_screen";

/** Where the overlay is on screen. */
export type Mode = "hidden" | "panel" | "orb" | "preview";

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
  /** Fired reminders awaiting delivery, pulled on each open and acked on dismiss (ADR-0025). */
  readonly reminders: readonly DueReminder[];
  /** What the overlay knows about the brain connection, for the header indicator (`linkState`). */
  readonly link: LinkView;
  /**
   * Whether the assistant has looked at the user's screen during the turn in flight
   * (ADR-0029). Set by the `capture_screen` tool activity and cleared only when the turn ends,
   * so the indicator stays lit for the rest of the turn rather than blinking past with the
   * chip. This is a **consent surface**, which is part of why the capture tool ships without an
   * approval card: the user is told plainly, by the app, that a picture was taken.
   */
  readonly capturing: boolean;
  readonly seq: number;
  /**
   * Whether the user has acted on this overlay since mount (opened it, typed, switched, or
   * minted a new chat). Cold-start adoption (ADR-0021) only replaces the fresh boot chat while
   * this is still false, so an explicitly chosen new chat is never hijacked. `seq`/`messages`
   * cannot stand in for it: `newChat` leaves both at their pristine values.
   */
  readonly touched: boolean;
}

export type Action =
  | { readonly kind: "open" }
  | { readonly kind: "submit"; readonly text: string }
  | { readonly kind: "event"; readonly event: TurnEvent }
  | { readonly kind: "transportError"; readonly error: TransportError }
  | { readonly kind: "dismiss" }
  | { readonly kind: "stop" }
  | { readonly kind: "confirmAnswered"; readonly approved: boolean }
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
  | {
      readonly kind: "sessionDeleted";
      readonly sessionId: string;
      /** A fresh id for the fallback chat when the deleted one was the currently-open chat. */
      readonly fallbackSessionId: string;
    }
  | { readonly kind: "remindersLoaded"; readonly reminders: readonly DueReminder[] }
  | { readonly kind: "reminderDismissed"; readonly reminderId: string }
  | { readonly kind: "linkProbing" }
  | { readonly kind: "linkObserved"; readonly status: LinkStatus }
  | { readonly kind: "linkProbeEnded" }
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
    reminders: [],
    link: INITIAL_LINK,
    capturing: false,
    seq: 0,
    touched: false,
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
      return { ...state, mode: "panel", touched: true };
    case "submit":
      return submit(state, action.text);
    case "event": {
      // Any event at all is the brain serving, so the turn keeps the indicator honest for free:
      // no probe fires while a stream is arriving. The identity check keeps a no-op event a
      // no-op (a late confirm request on a dead turn must not resurrect anything).
      const next = applyEvent(state, action.event);
      const link = linkServing(state.link);
      return link === state.link ? next : { ...next, link };
    }
    case "transportError":
      // The turn ends *and* the indicator learns: this is the failure the user is looking at.
      return { ...endTurn(state, action.error.message), link: linkFailed(state.link, action.error) };
    case "linkProbing":
      return { ...state, link: linkProbing(state.link) };
    case "linkObserved":
      return { ...state, link: linkObserved(action.status) };
    case "linkProbeEnded":
      return { ...state, link: linkProbeEnded(state.link) };
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
    case "confirmAnswered":
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
        touched: true,
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
    case "sessionDeleted":
      return deleteSession(state, action.sessionId, action.fallbackSessionId);
    case "remindersLoaded":
      // Each open re-reads: the brain is the authority on what is still deliverable, so the
      // list is replaced wholesale rather than merged (a reminder acked elsewhere leaves).
      return { ...state, reminders: action.reminders };
    case "reminderDismissed":
      // Optimistic: the card goes now and the ack rides the bridge. A lost ack means the
      // brain still holds it, and the next open surfaces it again (ADR-0025). Filtering an
      // unknown id is a no-op, so a double-click or a stale card cannot corrupt the list.
      return {
        ...state,
        reminders: state.reminders.filter((r) => r.reminderId !== action.reminderId),
      };
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
    touched: true,
    title,
    messages: [...state.messages, user, assistant],
    seq: state.seq + 2,
  };
}

function applyEvent(state: OverlayState, event: TurnEvent): OverlayState {
  switch (event.kind) {
    case "delta":
      return patchStreaming(state, (m) => ({ ...m, content: m.content + event.text }));
    case "toolActivity": {
      // The chip is emitted just BEFORE the dispatch, so this flag means "a capture was asked
      // for this turn", never "a capture happened": the outcome (host refused, body unreachable,
      // a gated capture declined) never crosses the seam. `CaptureDot`'s label says exactly that
      // and no more.
      const lit = state.capturing || event.toolName === CAPTURE_SCREEN_TOOL;
      const chipped = patchStreaming(state, (m) => ({
        ...m,
        tool: `${event.toolName}: ${event.summary}`,
      }));
      return { ...chipped, capturing: lit };
    }
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
function endTurn(state: OverlayState, error: string | null): OverlayState {
  const ended = patchStreaming(state, (m) => ({ ...m, streaming: false, error }));
  return {
    ...ended,
    mode: state.mode === "orb" ? "preview" : state.mode,
    pendingConfirm: null,
    // The turn is over, so the picture it took is out of context: the indicator goes out with
    // it rather than persisting into a turn that never looked at anything.
    capturing: false,
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
