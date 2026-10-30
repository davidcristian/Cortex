# A turn refused as deleted while the overlay is away raises an empty preview

**Status:** open, actionable
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Verified:** 2026-10-30

A turn that ends as `session_deleted` resets the overlay to a new chat with the turn's text in the
composer (`turnFoundDeleted` in `sessionState.ts`). The `failed` event is folded first, and
`endTurn` raises an orb, or a hidden overlay whose turn ran, to `preview`. The reset then empties
`messages`, so the raised card has no reply and no error: `Preview.tsx` shows an empty "Open reply"
card that fades after `PREVIEW_MS` and says nothing about the refusal.

The brain refuses before any model call, so the window is the time from submit to the refusal.
That is short on a healthy store and grows with the history read's retries while Redis is failing,
which is the case a lost delete reply comes from. This follows from the code and was not
reproduced on the real shell.

## What to do

1. Pick what a refused turn shows when the overlay is away. Recommended: open the panel, which
   shows the new chat with the text ready to send and speaks the notice. The alternatives are
   leaving the overlay hidden with the text parked, or a preview showing the refusal's message
   over the new chat. This is a visual pick, so propose it with a screenshot before building.
2. Build the pick in `turnFoundDeleted` with a Vitest case for each starting mode.

## History

- 2026-10-30: filed while building the overlay's recovery from a turn that ends as
  `session_deleted`, which covers the open panel but not an orb or a hidden overlay.
