import { parkDraft } from "./drafts";
import type { OverlayState } from "./overlayState";
import { NEW_CHAT_TITLE } from "./sessionState";
import { type Picture, type ReadPicture, addPictures } from "./pictures";

/** The composer's pictures, kept beside the drafts. */
export interface PictureState {
  /** Pictures waiting to be sent, keyed by session id like the drafts. */
  readonly waiting: Readonly<Record<string, readonly Picture[]>>;
  /** What the composer says about its pictures: the brain's refusal, or why one was left out. */
  readonly note: string | null;
  /** The turn in flight's text and pictures, handed back if the brain refuses a picture. */
  readonly sent: { readonly text: string; readonly pictures: readonly Picture[] } | null;
}

export const NO_PICTURES: PictureState = { waiting: {}, note: null, sent: null };

/** The pictures waiting under `sessionId`. */
export function waitingOf(pictures: PictureState, sessionId: string): readonly Picture[] {
  return pictures.waiting[sessionId] ?? [];
}

function withWaiting(
  pictures: PictureState,
  sessionId: string,
  waiting: readonly Picture[],
): PictureState["waiting"] {
  const rest = Object.entries(pictures.waiting).filter(([id]) => id !== sessionId);
  return Object.fromEntries(waiting.length === 0 ? rest : [...rest, [sessionId, waiting]]);
}

/** Adds read pictures to the chat on screen, numbering them from `seq`. */
export function attach(
  state: OverlayState,
  read: readonly ReadPicture[],
  problem: string | null,
): OverlayState {
  const incoming = read.map((picture, index) => ({ ...picture, id: `p${state.seq + index}` }));
  const added = addPictures(waitingOf(state.pictures, state.sessionId), incoming);
  const waiting = withWaiting(state.pictures, state.sessionId, added.pictures);
  const note = added.overflow ?? problem;
  return { ...state, seq: state.seq + read.length, pictures: { ...state.pictures, waiting, note } };
}

/** Removes one waiting picture from the chat on screen, and the note with it. */
export function detach(state: OverlayState, id: string): OverlayState {
  const kept = waitingOf(state.pictures, state.sessionId).filter((picture) => picture.id !== id);
  const waiting = withWaiting(state.pictures, state.sessionId, kept);
  return { ...state, pictures: { ...state.pictures, waiting, note: null } };
}

/** Moves the chat's waiting pictures into the turn being sent with `text`. */
export function send(state: OverlayState, text: string): PictureState {
  const pictures = waitingOf(state.pictures, state.sessionId);
  const waiting = withWaiting(state.pictures, state.sessionId, []);
  return { waiting, note: null, sent: { text, pictures } };
}

/** Hands a refused turn's text and pictures back to the composer with the brain's reason, and
 *  takes the exchange out of the log, since the brain stored none of it. */
export function refused(
  ended: OverlayState,
  sent: PictureState["sent"],
  reason: string,
): OverlayState {
  if (sent === null) {
    return ended;
  }
  // Text typed since the send stays, so the sent text goes back only into an empty field.
  const typed = ended.drafts[ended.sessionId] ?? "";
  const drafts = typed === "" ? parkDraft(ended.drafts, ended.sessionId, sent.text) : ended.drafts;
  const back = addPictures(sent.pictures, waitingOf(ended.pictures, ended.sessionId)).pictures;
  const waiting = withWaiting(ended.pictures, ended.sessionId, back);
  const messages = ended.messages.slice(0, -2);
  const title = messages.length === 0 ? NEW_CHAT_TITLE : ended.title;
  const pictures = { waiting, note: reason, sent: null };
  return { ...ended, messages, title, drafts, pictures };
}
