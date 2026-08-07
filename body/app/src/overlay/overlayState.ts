import type {
  DueReminder,
  LinkStatus,
  SessionMessage,
  SessionSummary,
  TransportError,
  TurnEvent,
} from "../bridge/types";
import { closeConsole, openConsole, toggleConsole, toggleSwitcher } from "./chromeState";
import { type Drafts, parkDraft } from "./drafts";
import {
  INITIAL_LINK,
  type LinkView,
  linkFailed,
  linkObserved,
  linkProbeEnded,
  linkProbing,
  linkServing,
} from "./linkState";
import { type Notice, reminderDismissed, speak } from "./notice";
import { NEW_CHAT_TITLE, adoptSession, deleteSession, newChat, openSession } from "./sessionState";
import {
  type CaptureClaim,
  type Message,
  type PendingConfirm,
  applyEvent,
  endTurn,
  isTurnActive,
  submit,
} from "./turnState";

// The overlay's pure state + reducer (ADR-0011, design/overlay-ux.md §4). Kept out of React so
// the interaction model (folding a Converse turn's events into messages, and the
// dismiss-while-streaming → orb → preview mode machine) is exhaustively testable. Components
// dispatch actions and render the result; animation lives in CSS. The three long halves live beside
// this file and are re-exported below, so a component still has one import: the session-switching
// helpers in `sessionState.ts`, the turn fold (what a message is, how its events apply) in
// `turnState.ts`, and the panel's own sections, the switcher list and the console's tabs, in
// `chromeState.ts`. Splitting them is what keeps all four under the line cap.

export { draftOf } from "./drafts";
export { cycleTarget } from "./sessionState";
export { CAPTURE_SCREEN_TOOL, isTurnActive, latestReply } from "./turnState";
export type { CaptureClaim, Message, PendingConfirm } from "./turnState";

/** Where the overlay is on screen. */
export type Mode = "hidden" | "panel" | "orb" | "preview";

/**
 * The console's tabs, in strip order. The console is the panel's one non-chat view (ADR-0035):
 * appearance and the shortcut list are two faces of it rather than two views, so there is one
 * thing open at a time and Esc has one thing to close. Exported as the list, not just the union,
 * because the tab strip and the panel's router both walk it.
 */
export const CONSOLE_TABS = ["appearance", "shortcuts"] as const;

export type ConsoleTab = (typeof CONSOLE_TABS)[number];

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
  /** Which console tab the panel is showing, or null while it is on the chat. One field, because
   *  the console is one view with a tab strip (ADR-0032, ADR-0035): appearance and the shortcut
   *  list cannot both be open, and Esc leaves in a single press from either. */
  readonly consoleTab: ConsoleTab | null;
  /** The approval the current turn is paused on, if any (ADR-0022). */
  readonly pendingConfirm: PendingConfirm | null;
  /** What the overlay's live region has to say about what just happened to the panel: the
   *  conversation that arrived, a list that shrank under the reader, or both in one sentence when
   *  a delete did both. `null` when nothing is owed, which is a swap fired by a control already
   *  naming what it hands back (`notice.ts` carries the whole of what may go here). */
  readonly notice: Notice | null;
  /**
   * Which conversation-arrival the panel is showing, counted from the overlay's first. The caret
   * follows the conversation: every arrival puts focus in the composer, where a summon already puts
   * it, and `Composer` holds the whole of that rule. A count rather than the session id, because
   * re-selecting the chat already open is still an arrival and still takes its own row away, and
   * rather than a flag, because two arrivals in a row have to read as two events.
   *
   * Unlike the notice beside it this is NOT decided per door (`notice.ts`): every gesture that
   * replaces the conversation wants the caret in one place, so each arm answers for all of its own
   * doors and nothing travels with the action. Cold-start adoption is the one swap that does not
   * count, having no gesture behind it to answer and running only while the panel is untouched.
   */
  readonly arrival: number;
  /** What the composer is holding for each conversation, keyed by session id (`drafts.ts`). The
   *  field on screen is this map's entry for `sessionId`, so a swap hands the arriving chat its own
   *  text in the same commit that swaps and no arm has to move anything. */
  readonly drafts: Drafts;
  /** Fired reminders awaiting delivery, pulled on each open and acked on dismiss (ADR-0025). */
  readonly reminders: readonly DueReminder[];
  /** What the overlay knows about the brain connection, for the header indicator (`linkState`). */
  readonly link: LinkView;
  /**
   * How far this turn's screen-capture claim has climbed, or `null` if nothing was asked for
   * (ADR-0029). Raised to `"asked"` by the `capture_screen` tool activity, to `"read"` by the
   * outcome that settles it, and cleared only when the turn ends, so the indicator stays lit
   * for the rest of the turn rather than blinking past with the chip. This is a **consent
   * surface**, which is part of why the capture tool ships without an approval card: the user
   * is told plainly, by the app, that a picture was taken. Within a turn it only ever climbs,
   * because a privacy indicator may over-report and may never under-report.
   */
  readonly capture: CaptureClaim | null;
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
  /** The composer's field changed. Parked under whichever chat is on screen, so the text is
   *  already where it belongs by the time any swap arm runs (`drafts.ts`). */
  | { readonly kind: "draft"; readonly text: string }
  | { readonly kind: "event"; readonly event: TurnEvent }
  | { readonly kind: "transportError"; readonly error: TransportError }
  | { readonly kind: "dismiss" }
  | { readonly kind: "stop" }
  | { readonly kind: "confirmAnswered"; readonly approved: boolean }
  | { readonly kind: "previewFade" }
  | {
      readonly kind: "newChat";
      readonly sessionId: string;
      /** Whether the fresh chat is announced: true for Ctrl+N, false for the header's pencil,
       *  whose own label is the name of what arrives (`notice.ts`). */
      readonly announce: boolean;
    }
  | { readonly kind: "sessionsLoaded"; readonly sessions: readonly SessionSummary[] }
  | {
      readonly kind: "openSession";
      readonly sessionId: string;
      readonly messages: readonly SessionMessage[];
      /** Whether the arriving chat is announced: true for the cycle keys and a reminder's open
       *  control, false for a switcher row, which is already named for it (`notice.ts`). */
      readonly announce: boolean;
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
  | {
      readonly kind: "toggleSwitcher";
      /** Whether the opened list says what it holds: true for Ctrl+K, false for the header's
       *  chats button, which carries `aria-expanded` under the caret that pressed it
       *  (`chromeState.ts`). */
      readonly announce: boolean;
    }
  | { readonly kind: "openConsole"; readonly tab: ConsoleTab }
  | { readonly kind: "toggleConsole"; readonly tab: ConsoleTab }
  | { readonly kind: "closeConsole" };

/** A fresh, empty overlay state for `sessionId` (a new chat). */
export function createInitialState(sessionId: string): OverlayState {
  return {
    mode: "hidden",
    sessionId,
    title: NEW_CHAT_TITLE,
    messages: [],
    sessions: [],
    switcherOpen: false,
    consoleTab: null,
    pendingConfirm: null,
    notice: null,
    arrival: 0,
    drafts: {},
    reminders: [],
    link: INITIAL_LINK,
    capture: null,
    seq: 0,
    touched: false,
  };
}

export const initialState: OverlayState = createInitialState("");

export function reduce(state: OverlayState, action: Action): OverlayState {
  switch (action.kind) {
    case "open":
      // A summon always arrives at the chat. Clearing the console HERE and not on dismiss is the
      // whole trick: the panel fades out wearing whatever it had on, instead of morphing back to
      // the chat first and then fading, which read as the window changing its mind on the way out.
      return { ...state, mode: "panel", consoleTab: null, touched: true };
    case "submit":
      return submit(state, action.text);
    case "draft":
      // Typing is the user acting on the overlay, which `touched` has always claimed to cover and
      // until now could not: nothing dispatched on a keystroke, so a cold-start adoption could
      // replace the chat under a sentence somebody was in the middle of. Now it cannot.
      return {
        ...state,
        touched: true,
        drafts: parkDraft(state.drafts, state.sessionId, action.text),
      };
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
      // console is deliberately LEFT OPEN: it is closed by the next summon instead, so the panel
      // fades out as it stands rather than morphing back to the chat under a fading window.
      return {
        ...state,
        mode: isTurnActive(state) ? "orb" : "hidden",
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
      return newChat(state, action.sessionId, action.announce);
    case "sessionsLoaded":
      return { ...state, sessions: action.sessions };
    case "openSession":
      return openSession(state, action.sessionId, action.messages, action.announce);
    case "adoptSession":
      return adoptSession(state, action.sessionId, action.messages);
    case "sessionDeleted":
      return deleteSession(state, action.sessionId, action.fallbackSessionId);
    case "remindersLoaded":
      // Each open re-reads: the brain is the authority on what is still deliverable, so the
      // list is replaced wholesale rather than merged (a reminder acked elsewhere leaves).
      return { ...state, reminders: action.reminders };
    case "reminderDismissed": {
      // Optimistic: the card goes now and the ack rides the bridge. A lost ack means the brain
      // still holds it, and the next open surfaces it again (ADR-0025). Filtering an unknown id
      // is a no-op, so a double-click or a stale card cannot corrupt the list, and the region is
      // told the same way: a row that did not leave raises no sentence about one (`notice.ts`).
      // The stack is the overlay's other list that shrinks under the hand, so it speaks for the
      // same reason the switcher does, and its last row is the one that also takes the section.
      const reminders = state.reminders.filter((r) => r.reminderId !== action.reminderId);
      return reminders.length === state.reminders.length
        ? state
        : { ...state, reminders, notice: speak(state.notice, [reminderDismissed(reminders.length)]) };
    }
    case "toggleSwitcher":
      return toggleSwitcher(state, action.announce);
    case "openConsole":
      return openConsole(state, action.tab);
    case "toggleConsole":
      return toggleConsole(state, action.tab);
    case "closeConsole":
      return closeConsole(state);
  }
}
