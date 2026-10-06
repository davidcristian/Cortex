# The preview of a failed turn fades like a finished one

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Verified:** 2026-10-06

[Overlay UX](../../design/overlay-ux.md) section 4 says a failed turn previews as a red-tinted card
that does not fade on its own. The code does neither. `endTurn` in `overlay/turnState.ts` writes the
error onto the message and raises the preview, but the `previewFade` case in
`overlay/overlayState.ts` and the timer in `overlay/useOverlay.ts` check only the pending approval
and whether the turn still runs, so the card fades after `PREVIEW_MS` (6 s). `components/Preview.tsx`
shows `latestReply`, the message's content, which for a turn that failed before any text is empty,
and nothing tints the card.

**Do.** Keep the preview of a failed turn up until it is clicked or dismissed: the reducer and the
timer both ask whether the latest reply has an `error`, and `Preview` gets that error to show and
no countdown bar, as it has none for a pending approval. The tint is a visual pick, so propose it
with an alternative before writing it into `overlay.css`. All of this is covered code in
`body/app/src`.

## History

- 2026-10-06: filed while the preview of a pending approval was fixed; reading the preview's code
  for that showed the failed turn's case is not built.
