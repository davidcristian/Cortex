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
import { NO_PICTURES, type PictureState, attach, detach } from "./pictureState";
import type { ReadPicture } from "./pictures";
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

// The overlay's pure state and reducer, kept out of React so the interaction model can be tested
// on its own. Three long halves live beside this file and are re-exported below, so a component
// still has one import: session switching, the turn fold, and the panel's own sections.

export { draftOf } from "./drafts";
export { cycleTarget } from "./sessionState";
export { CAPTURE_SCREEN_TOOL, isTurnActive, latestReply } from "./turnState";
export type { CaptureClaim, Message, PendingConfirm } from "./turnState";

/** Where the overlay is on screen. */
export type Mode = "hidden" | "panel" | "orb" | "preview";

/** The console's tabs, in strip order. Exported as the list rather than only the union, because
 *  the tab strip and the panel's router both walk it. */
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
   *  the two tabs cannot both be open and Esc leaves from either in a single press. */
  readonly consoleTab: ConsoleTab | null;
  /** The approval the current turn is paused on, if any (ADR-0022). */
  readonly pendingConfirm: PendingConfirm | null;
  /** What the overlay's live region has to say about what just happened to the panel: the
   *  conversation that arrived, a list that shrank under the reader, or both in one sentence when
   *  a delete did both. */
  readonly notice: Notice | null;
  /** Which conversation-arrival the panel is showing, counted from the overlay's first. A count
   *  rather than the session id, because re-selecting the chat already open is still an arrival,
   *  and not a flag, because two arrivals in a row have to read as two events. */
  readonly arrival: number;
  /** What the composer is holding for each conversation, keyed by session id (`drafts.ts`). The
   *  field on screen is this map's entry for `sessionId`, so a swap hands the arriving chat its own
   *  text in the same commit. */
  readonly drafts: Drafts;
  /** The pictures waiting in the composer, and the one turn's that may be handed back. */
  readonly pictures: PictureState;
  /** Fired reminders awaiting delivery, pulled on each open and acked on dismiss (ADR-0025). */
  readonly reminders: readonly DueReminder[];
  /** What the overlay knows about the brain connection, for the header indicator (`linkState`). */
  readonly link: LinkView;
  /** How far this turn's screen-capture claim has climbed, or `null` if nothing was asked for. It
   *  is cleared only when the turn ends, and within a turn it only ever climbs, because a privacy
   *  indicator may over-report and may never under-report. */
  readonly capture: CaptureClaim | null;
  readonly seq: number;
  /** Whether the user has acted on this overlay since mount (opened it, typed, switched, or
   *  started a new chat). `seq` and `messages` cannot stand in for it, because starting a new chat
   *  leaves both at their initial values. */
  readonly touched: boolean;
}

export type Action =
  | { readonly kind: "open" }
  | { readonly kind: "submit"; readonly text: string }
  /** The composer's field changed. */
  | { readonly kind: "draft"; readonly text: string }
  | {
      readonly kind: "attach";
      readonly pictures: readonly ReadPicture[];
      readonly problem: string | null;
    }
  | { readonly kind: "detach"; readonly id: string }
  | { readonly kind: "event"; readonly event: TurnEvent }
  | { readonly kind: "transportError"; readonly error: TransportError }
  | { readonly kind: "dismiss" }
  | { readonly kind: "stop" }
  | { readonly kind: "confirmAnswered"; readonly approved: boolean }
  | { readonly kind: "previewFade" }
  | {
      readonly kind: "newChat";
      readonly sessionId: string;
      /** Whether the fresh chat is announced: true for Ctrl+N, false for the header's pencil, whose
       *  own label is the name of what arrives (`notice.ts`). */
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
       *  chats button, which has `aria-expanded` under the caret that pressed it. */
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
    pictures: NO_PICTURES,
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
      // A summon always arrives at the chat. Clearing the console here rather than on dismiss is
      // what lets the panel fade out showing whatever it had up.
      return { ...state, mode: "panel", consoleTab: null, touched: true };
    case "submit":
      return submit(state, action.text);
    case "draft":
      // Typing is the user acting on the overlay, so a cold-start adoption cannot replace the chat
      // under a sentence somebody is in the middle of.
      return {
        ...state,
        touched: true,
        drafts: parkDraft(state.drafts, state.sessionId, action.text),
      };
    case "attach":
      return attach({ ...state, touched: true }, action.pictures, action.problem);
    case "detach":
      return detach(state, action.id);
    case "event": {
      // Any event at all is the brain serving, so the indicator stays current with no probe while
      // a stream is arriving.
      const next = applyEvent(state, action.event);
      const link = linkServing(state.link);
      return link === state.link ? next : { ...next, link };
    }
    case "transportError":
      return { ...endTurn(state, action.error.message), link: linkFailed(state.link, action.error) };
    case "linkProbing":
      return { ...state, link: linkProbing(state.link) };
    case "linkObserved":
      return { ...state, link: linkObserved(action.status) };
    case "linkProbeEnded":
      return { ...state, link: linkProbeEnded(state.link) };
    case "dismiss":
      // Dismissing drops any pending approval with it, since walking away is a deny and the brain
      // fails closed on its own timeout. The console is left open, and the next summon clears it.
      return {
        ...state,
        mode: isTurnActive(state) ? "orb" : "hidden",
        pendingConfirm: null,
      };
    case "stop":
      // The user cancelled: end the streaming reply in place, keeping the partial text, and stay in
      // the panel. Dismiss minimizes to the orb instead.
      return endTurn(state, null);
    case "confirmAnswered":
      return { ...state, pendingConfirm: null };
    case "previewFade":
      // A pending approval waits to be seen, and a still-streaming turn is never faded from under.
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
      // Each open re-reads: the brain is the authority on what is still deliverable, so the list is
      // replaced whole rather than merged.
      return { ...state, reminders: action.reminders };
    case "reminderDismissed": {
      // The card goes now and the ack is sent over the bridge. A lost ack means the brain still
      // holds the reminder and the next open shows it again. Filtering an unknown id does nothing,
      // so a double-click or a stale card cannot corrupt the list.
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
