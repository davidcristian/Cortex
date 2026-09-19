# Out-of-window authoritative title

**Status:** open, dead until a consumer
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)
**Trigger:** A second caller that opens a chat by id from outside the loaded window, beside the reminder card's open control, such as toast activation routing once `NotifyRequest` carries a `session_id` (R-230) or a search.
**Verified:** 2026-09-19

Opened 2026-07-16 behind the header-title carry that closed
[179](179-open-chat-header-title.md). The carry reads the title from `state.sessions`, so a chat
**not** in the loaded recency window still derives its header locally. The only path today that
opens a chat absent from that window is a reminder deep-link (`Reminders.tsx` "open chat") to a
chat that has fallen outside the loaded `listSessions(50)`; the switcher shows no row for such a
chat either, so the disagreement is not user-visible, which is exactly why the overlay-only carry
was preferred over the proto field. The authoritative closure is the `title` field on
`GetSessionMessages` that entry named (the same reply
[118](118-reasoning-thinking-status.md) would widen with a reasoning field, if its declined
re-display ever reopens), dead until a second caller opens an out-of-window chat
beside the reminder card (toast activation routing once `NotifyRequest` carries a `session_id`, or
a search).
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
- 2026-09-19: Re-derived, and the code claims from 2026-09-13 all hold: `headerTitle` in
  `body/app/src/overlay/sessionState.ts` still falls back to `titleFor`, `GetSessionMessagesReply`
  still carries `messages` alone, `SESSION_LIST_LIMIT` is still 50, and `Reminders.tsx` is still the
  only caller of `onSelectSession` with an id the loaded list may not hold. Two things were wrong.
  The trigger's last example, "a deep-link by id", was met the day it was written, since the
  reminder card's open control is a deep-link by id and the entry names it as the path that exists,
  so the trigger now asks for a second caller. And 118 does not want this read path widened: it
  landed on 2026-07-06, and the reasoning re-display that would add a field to this reply was
  declined on 2026-07-16 for want of a consumer, so the parenthesis now says that. The trigger has
  not fired: 230 is still dead, `NotifyRequest` has no `session_id`, and no search exists. There is
  no circle, since 230 waits on nothing here.
