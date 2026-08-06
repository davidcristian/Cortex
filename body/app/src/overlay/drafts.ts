/** Unsent composer text by session id, so swapping away from a chat parks what was typed into it
 *  and coming back restores it. A chat with nothing typed into it is absent rather than stored as
 *  an empty string, so this does not grow an entry per chat the user merely visits. */
export type Drafts = Readonly<Record<string, string>>;

/** What the composer shows for `sessionId`: its parked text, or an empty field. */
export function draftOf(drafts: Drafts, sessionId: string): string {
  return drafts[sessionId] ?? "";
}

/** Park `text` under `sessionId`. Emptying the field drops the entry, and re-parking the text
 *  already held returns the same map, so a keystroke that changes nothing allocates nothing. */
export function parkDraft(drafts: Drafts, sessionId: string, text: string): Drafts {
  if (text === "") {
    return dropDraft(drafts, sessionId);
  }
  return drafts[sessionId] === text ? drafts : { ...drafts, [sessionId]: text };
}

/** Forget `sessionId`'s draft: its text was sent, or its chat was deleted. An unknown id returns
 *  the same map. */
export function dropDraft(drafts: Drafts, sessionId: string): Drafts {
  if (!(sessionId in drafts)) {
    return drafts;
  }
  return Object.fromEntries(Object.entries(drafts).filter(([id]) => id !== sessionId));
}
