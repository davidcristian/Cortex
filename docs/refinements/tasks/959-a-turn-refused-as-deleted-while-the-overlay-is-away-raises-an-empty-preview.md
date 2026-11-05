# A turn refused as deleted while the overlay is away raises an empty preview

**Status:** open, actionable
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Verified:** 2026-11-05

A turn that ends as `session_deleted` resets the overlay to a new chat with the turn's text in the
composer (`turnFoundDeleted` in `sessionState.ts`). The `failed` event is folded first, and
`endTurn` raises an orb, or a hidden overlay whose turn ran, to `preview`. The reset then empties
`messages`, so the raised card has no reply and no error: `Preview.tsx` shows an empty "Open reply"
card that fades after `PREVIEW_MS` and says nothing about the refusal.

The brain refuses before any model call, so the window is the time from submit to the refusal.
That is short on a healthy store and grows with the history read's retries while Redis is failing,
which is the case a lost delete reply comes from. The real Linux shell shows it: the raised card
has the draining bar and no text, and the window hides when the fade ends.

## What to do

1. Pick what a refused turn shows when the overlay is away. This is a visual pick for the
   maintainer; the frames named in History show today's empty card and the recovered panel.
   - **Open the panel** (recommended): it shows the new chat with the text ready to send, as a
     summon after the fade shows it today, and speaks the notice.
   - **Stay hidden** with the text parked, so the overlay shows nothing until the next summon.
   - **A preview with the refusal's message** over the new chat, so the card says why the turn
     did not run and a click opens the panel.
2. Build the pick in `turnFoundDeleted` with a Vitest case for each starting mode.

## History

- 2026-10-30: filed while building the overlay's recovery from a turn that ends as
  `session_deleted`, which covers the open panel but not an orb or a hidden overlay.
- 2026-11-05: reproduced on the real Linux shell against the stack brain. After a first turn in a
  new chat, the chat's id was added to `cortex:sessions:deleted` and Redis was paused with
  `docker pause`; a second message was sent and Escape dismissed the overlay to the orb while the
  turn waited. On unpause the brain logged `refusing a turn sent to a deleted chat`, and the
  overlay raised a preview with the bar and no text, then hid. A summon showed "New chat" with the
  sent text in the composer. Frames `p2a.png` (orb), `p2b.png` (empty card), `p2d.png` (hidden)
  and `p3.png` (summoned panel), with the driver `p2.sh`, are in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/7993c5bc-88df-4188-a4c9-74349733b88c/scratchpad/slot17/`.
