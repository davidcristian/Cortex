// The unsent text each conversation is holding (ADR-0035 addendum): the composer's field, keyed by
// the chat it was typed into. A half-typed question belongs to the conversation it was started in,
// so swapping away parks it and coming back restores it.
//
// WHY THE MAP IS HERE AND NOT BEHIND A PORT. The repo's hard rule is that state survives a model
// swap, meaning no conversation state, task state or working memory inside a model-server process
// or a model's KV cache. This is in the body's own reducer, which a model swap cannot reach, so
// the rule is satisfied by construction rather than by storage. What a store would buy on top is
// survival of a body RESTART, and a draft does not earn that: it is text nobody has sent, no
// surface anywhere promises it is kept, and nothing but the field it was typed in can read it. It
// is the same category as the switcher being open, the console's tab, the log's scroll position
// and the switcher row's own half-typed rename, all of which die with the process today. Buying
// durability costs a proto message, a brain-side arm, an adapter, a contract test and an eviction
// policy, spent per keystroke over gRPC.
//
// It is in the REDUCER rather than in `Composer`'s own state so that decision stays cheap to
// revisit, and because two things the component cannot see need it: the delete cascade has to take
// a deleted chat's draft with it, and a swap has to hand the arriving chat its own text in the
// commit that swaps, with no effect in between to flash the outgoing one. If a draft ever must
// survive a restart it hydrates and persists exactly where `messages` does.
//
// The word is overloaded in this tree and deliberately kept: an approval's `argumentsJson` is "the
// draft" in ADR-0022's vocabulary (`components/draftValue.ts`), and a switcher row's in-progress
// label is a `draft` local. Both are unrelated to this one, which is the composer's, and which is
// what every doc in the overlay already calls a draft.

/** Unsent composer text by session id. A chat with nothing typed in it is ABSENT, never `""`:
 *  that is what keeps this from growing an entry per chat the user merely visits. What is left
 *  grows only by the user typing into a chat and leaving without sending, and each entry leaves
 *  again when its text is sent, when its chat is deleted, or when the field is emptied by hand. */
export type Drafts = Readonly<Record<string, string>>;

/** What the composer shows for `sessionId`: its parked text, or an empty field. */
export function draftOf(drafts: Drafts, sessionId: string): string {
  return drafts[sessionId] ?? "";
}

/** Park `text` under `sessionId`. Emptying the field drops the entry rather than storing `""`,
 *  and re-parking the text already held returns the same map, so a keystroke that changes nothing
 *  (a resize re-measure, a repeat) allocates nothing. */
export function parkDraft(drafts: Drafts, sessionId: string, text: string): Drafts {
  if (text === "") {
    return dropDraft(drafts, sessionId);
  }
  return drafts[sessionId] === text ? drafts : { ...drafts, [sessionId]: text };
}

/** Forget `sessionId`'s draft: its text was sent, or its chat was deleted. Unknown ids are a
 *  no-op returning the same map, so a delete of a chat nobody typed in costs nothing. */
export function dropDraft(drafts: Drafts, sessionId: string): Drafts {
  if (!(sessionId in drafts)) {
    return drafts;
  }
  return Object.fromEntries(Object.entries(drafts).filter(([id]) => id !== sessionId));
}
