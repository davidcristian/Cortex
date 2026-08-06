import type { SessionMessage, SessionSummary } from "../bridge/types";
import { dropDraft } from "./drafts";
import { speak } from "./notice";
import type { OverlayState } from "./overlayState";
import type { Message } from "./turnState";

// Session-switching halves of the overlay state (ADR-0021): minting a fresh chat, hydrating a
// stored one into the panel, adopting the most recent on cold start, cycling between recent chats,
// and the title derivation they share with `turnState`'s `submit`. Split from `overlayState.ts`
// (which re-exports the pieces components use) to keep every one of them under the repo line cap;
// only types cross back, so the runtime import graph stays one-directional.
//
// All four swap arms live together because they answer the same three questions the same way, and
// reading one is reading the others: whether the arriving chat is announced (`notice.ts`), that its
// arrival takes the caret with it (`arrival`), and what becomes of the draft the outgoing chat was
// holding. That last one is nothing at all for three of them: the composer's text is keyed by
// session id and parked as it is typed (`drafts.ts`), so a chat leaving keeps what it was holding
// and a chat arriving is handed its own, with no arm doing anything. Only a DELETE has work,
// having taken away the conversation a draft belonged to.

export const NEW_CHAT_TITLE = "New chat";
/**
 * The character bound on a title, the same number the brain's `cortex_core.sessions.TITLE_MAX`
 * bounds every listed title to, and tied to it by `scripts/crosscheck.py` so neither can move
 * alone. It has to be the same number rather than merely a number, because `deriveTitle` below is
 * a STAND-IN for the brain's derivation and not a bound of its own: it names a chat the brain has
 * not listed yet, and the moment that chat is listed the switcher row beside the header carries
 * the brain's rendering of the same first message. At 32 against 48 those two strings differed on
 * screen at once, a 42-character first message reading in full in the row and cut at 32 in the
 * header, in a header box measured wider than the row (339px against 314px at a 900px viewport,
 * fitting 42 characters against 39), so the shorter cut was not answering less room.
 */
const TITLE_MAX = 48;

/** The live title for a chat the brain has not listed yet: the brain's rule, applied locally.
 *  Collapse runs of whitespace to single spaces, then past `TITLE_MAX` characters cut and append
 *  one ellipsis, which is what `_one_line` in `cortex_core.sessions` does to the same text. Once
 *  the chat is listed, the brain's own title replaces this one (`headerTitle`), and the two read
 *  alike because the rule and the bound are the same on both sides. */
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

/**
 * The header title for a chat being loaded into the panel (ADR-0021 titles addendum). When the
 * chat is in the loaded switcher list, this is the switcher's own `SessionSummary.title` for it,
 * so the open-chat header shows exactly the switcher row: the brain's authoritative title (a
 * stored generated title, a user rename, or the brain-side first-message derivation, each bounded
 * brain-side). Reading both surfaces off the one `sessions` snapshot makes them equal by
 * construction, rather than re-deriving the header locally, which drifts from the switcher on a
 * rename, on a longer brain-side truncation bound, or on a generated title. A chat not in the
 * loaded list (reachable today only by a reminder deep-link to a chat outside the recency window,
 * whose row the switcher cannot show either) has no summary in hand and falls back to the local
 * first-message derivation.
 */
function headerTitle(
  sessions: readonly SessionSummary[],
  sessionId: string,
  messages: readonly SessionMessage[],
): string {
  const summary = sessions.find((s) => s.sessionId === sessionId);
  return summary ? summary.title : titleFor(messages);
}

/**
 * Mint a fresh chat over whatever is on screen (ADR-0035 addendum, 2026-08-03). The console leaves
 * with the old chat. Both doors here, Ctrl+N and the header's pencil, are aimed at the conversation,
 * so they land in the conversation: the arm sets `mode: "panel"` for that reason, and leaving
 * `consoleTab` alone emptied the chat *behind* the console, which stayed up (the user's pick; Ctrl+N
 * is the reachable half of the pair, the pencil being under the console with the rest of the chat).
 * This is the opposite call from `dismiss` and for the opposite reason: the panel stays on screen
 * here, so the morph back to the chat is the movement that was asked for rather than one the window
 * makes on its way out.
 *
 * The two doors part company on one thing only, which is whether the swap is announced. The pencil
 * is labelled "New chat" and hands back exactly that string, so it stays silent; the keystroke names
 * nothing, so it speaks (`notice.ts`). They agree about focus, as every pair of doors on one arm
 * does: the empty chat arrives with the caret in it (`arrival`).
 *
 * And they agree about the draft, which needs no line here. The fresh id has nothing parked under
 * it, so the composer is empty; the sentence the user was half way through stays under the chat
 * they were half way through it in, and is waiting there when they cycle back (`drafts.ts`).
 */
export function newChat(state: OverlayState, sessionId: string, announce: boolean): OverlayState {
  return {
    ...state,
    mode: "panel",
    touched: true,
    sessionId,
    title: NEW_CHAT_TITLE,
    notice: announce ? speak(state.notice, NEW_CHAT_TITLE) : null,
    arrival: state.arrival + 1,
    messages: [],
    switcherOpen: false,
    consoleTab: null,
    pendingConfirm: null,
  };
}

/**
 * Load a stored chat into the panel: hydrate its messages, carry the switcher's title, and leave
 * the console the way `newChat` does (ADR-0035 addendum, 2026-08-03). The switcher row that
 * selects a chat is unreachable while the console is up, since the chat view is `display: none`
 * behind it, but Ctrl+Up and Ctrl+Down are global keys and cycle straight into this: without the
 * clear they loaded another conversation behind the standing console, which is the same
 * surprise the new-chat arm was answering and the same answer.
 *
 * `announce` is the caller's door, not this arm's decision, because the doors are three and the
 * arm is one: a cycle key and a reminder's open control speak, a switcher row does not
 * (`notice.ts`). What is announced is the title computed right here, so the live region and the
 * header cannot disagree about which chat arrived, in the same way the header and the switcher
 * row cannot (`headerTitle`).
 *
 * Focus is the arm's own decision and needs no flag, all three doors wanting the same landing: the
 * chat arrives with the caret in the composer (`arrival`, and `Composer` for why there). Two of
 * these doors are why that rule exists, a switcher row and a reminder's open control both sitting
 * inside a section this swap takes away.
 */
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
    notice: announce ? speak(state.notice, title) : null,
    arrival: state.arrival + 1,
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
 * panel and never takes a view off it. The console cannot be up here anyway, since reaching it
 * means summoning the panel and a summon sets `touched`, which is the guard below. The guard is
 * the reducer-evaluated `touched` flag: adoption applies only while the user has not acted on
 * the overlay since mount, so a racing summon, submit, cycle, or explicit new-chat wins (each
 * sets `touched`), and a StrictMode double-fired mount effect is idempotent. `seq`/`messages`
 * cannot stand in for `touched`: `newChat` leaves both pristine, so open then new-chat then
 * dismiss would otherwise read as an untouched boot and be hijacked.
 *
 * It is the one chat swap that says nothing, and it needs no flag to stay quiet: there is no
 * gesture behind it to answer, and it runs only while `touched` is false, which every door that
 * can raise a notice sets. So a restore cannot arrive over something said, and the notice it
 * carries forward is always the `null` it started at.
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
 * delete addendum). Deleting any other chat only drops its row. Deleting the CURRENTLY OPEN chat
 * must never leave a deleted transcript on screen, so the panel resets to a fresh empty chat in
 * place (the panel stays open, the switcher stays as it was so the user can keep managing chats),
 * taking `fallbackSessionId` for its identity: the reducer cannot mint ids, so the controller mints
 * one and hands it in. Either way `touched` is set, since deleting is the user acting on the overlay.
 *
 * The console is the one surface this leaves standing where its two neighbours clear it, and the
 * reason is the same reason the switcher stays open: a delete is fired from a switcher row, so the
 * user is managing chats rather than asking for one, and the surface they are working in survives
 * the write. That row is its only caller and the chat view is `display: none` behind the console,
 * so this is unreachable from there besides.
 *
 * That reset is a chat swap and it always announces, with no flag to say so, because it has only
 * the one door and that door names the wrong chat: the button pressed is "Confirm delete" plus the
 * title of the conversation LEAVING, which says nothing about the empty one taking its place
 * (`notice.ts`). Deleting any other chat swaps nothing and stays silent.
 *
 * It is a swap for focus too, and the reset counts as an arrival: the confirm button is inside the
 * row that leaves, so the caret goes to the composer of the chat that arrived rather than nowhere
 * (`arrival`). The switcher stays open behind it, which is deliberate above and unchanged here.
 *
 * It is also the ONE arm that touches a draft, and it does so on both of its paths, because a draft
 * belongs to a conversation and this is where a conversation stops existing (`drafts.ts`). Deleting
 * another chat drops the text parked under it, which nothing could ever reach again; deleting the
 * open one drops it too, and the empty chat taking its place is handed nothing, since the sentence
 * was about the transcript that just went away.
 */
export function deleteSession(
  state: OverlayState,
  sessionId: string,
  fallbackSessionId: string,
): OverlayState {
  const sessions = state.sessions.filter((s) => s.sessionId !== sessionId);
  const drafts = dropDraft(state.drafts, sessionId);
  if (sessionId !== state.sessionId) {
    return { ...state, sessions, drafts, touched: true };
  }
  return {
    ...state,
    sessions,
    drafts,
    touched: true,
    sessionId: fallbackSessionId,
    title: NEW_CHAT_TITLE,
    notice: speak(state.notice, NEW_CHAT_TITLE),
    arrival: state.arrival + 1,
    messages: [],
    pendingConfirm: null,
    seq: 0,
  };
}

/**
 * The session id to switch to when cycling from `currentId` by `delta`
 * (-1 = newer / previous, +1 = older / next), or `null` for no move.
 * `sessions` is newest-first. A current chat not in the list (a fresh, unsaved
 * chat) enters the list only on `+1` (into the most recent saved chat).
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
