# Out-of-window authoritative title

**Status:** open, dead until a consumer
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)
**Trigger:** A consumer that opens an out-of-window chat beside the switcher, such as toast activation routing once `NotifyRequest` carries a `session_id`, or a search or deep-link by id.
**Verified:** 2026-09-13

Opened 2026-07-16 behind the header-title carry that closed
[179](179-open-chat-header-title.md). The carry reads the title from `state.sessions`, so a chat
**not** in the loaded recency window still derives its header locally. The only path today that
opens a chat absent from that window is a reminder deep-link (`Reminders.tsx` "open chat") to a
chat that has fallen outside the loaded `listSessions(50)`; the switcher shows no row for such a
chat either, so the disagreement is not user-visible, which is exactly why the overlay-only carry
was preferred over the proto field. The authoritative closure is the `title` field on
`GetSessionMessages` that entry named (the same read path
[118](118-reasoning-thinking-status.md) independently wants widened), dead until a consumer that
opens an out-of-window chat beside the switcher exists (toast activation routing once
`NotifyRequest` carries a `session_id`, or a search / deep-link by id).
**Narrowed 2026-08-03 without being closed.** With the two `TITLE_MAX` declarations now equal and
tied to each other by `scripts/crosscheck.py`, the local derivation renders exactly what the brain
would have listed for the same first message, so the fallback no longer differs in *length*. What is still
open is what it cannot know: a user rename or a generated title stored against that chat, which
only the read path can carry. Measured on the reminder deep-link in Chromium, a chat outside the
loaded window opens with its first message derived locally, at the brain's bound.

## Trail

- 2026-07-16: Opened behind the overlay-only header-title carry that closed the open-chat
  consistency item.
- 2026-08-03: Narrowed without closing. With the two `TITLE_MAX` declarations equal, the local
  fallback renders exactly what the brain would have listed for the same first message, so
  what stays open is only what the fallback cannot know, a stored rename or a generated
  title.
- 2026-09-13: read against the tree and still true, with its two references to a neighbouring
  entry given that entry's number: they were written when this backlog was one document and an
  entry could be above another one. `headerTitle` still takes the loaded `SessionSummary.title`
  when the chat is in `state.sessions` and falls back to `titleFor` otherwise
  (`body/app/src/overlay/sessionState.ts`), `GetSessionMessagesReply` still carries messages and
  no title (`proto/body.proto`), and the catalog still loads 50 rows
  (`SESSION_LIST_LIMIT`, `body/app/src/overlay/useSessionCatalog.ts`). The trigger has not fired:
  the reminder card's open control is still the only caller that can name a chat outside that
  window, since the switcher rows and the two cycle keys all read from the loaded list, and toast
  activation routing is still dead for want of a `session_id` on `NotifyRequest`
  ([230](230-toast-activation-routing.md)).
