# The preview of a pending card is empty

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-10-06

A confirm card that arrives while the overlay is minimized raises the preview, which does not fade
while the question is open ([overlay UX](../../design/overlay-ux.md), the approval card). The
preview shows `latestReply(state)` and nothing else (`components/Preview.tsx`). A turn that calls
the tool before it writes any text has no reply yet, so the preview is an empty card, and its
countdown bar drains as if the card would fade, which it does not. On the Linux shell run of
2026-10-06 the empty card stayed for the whole 45 s wait and the action was denied on the timeout
([readings](../../readings/tauri-ipc-commands.md#the-commands-on-the-linux-shell)).

**Do.** When `pendingConfirm` is set, give the preview a line that says an approval is waiting and
names the tool, and leave out the countdown bar, since no countdown runs. The reducer already
knows both facts; the change is in `Preview.tsx` and its caller in `Overlay.tsx`, both covered.

## History

- 2026-10-06: filed by the Linux shell run of
  [H-004](../../host/tasks/004-confirm-card-over-ipc.md), which minimized the overlay with Escape
  and let a card time out.
