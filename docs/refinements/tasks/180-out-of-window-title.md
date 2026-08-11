# Out-of-window authoritative title

**Status:** open, dead until a consumer
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)
**Trigger:** A consumer that opens an out-of-window chat beside the switcher, such as toast activation routing once `NotifyRequest` carries a `session_id`, or a search or deep-link by id.

Opened 2026-07-16 behind the header-title carry above. The
carry reads the title from `state.sessions`, so a chat **not** in the loaded recency window still
derives its header locally. The only path today that opens a chat absent from that window is a
reminder deep-link (`Reminders.tsx` "open chat") to a chat that has fallen outside the loaded
`listSessions(50)`; the switcher shows no row for such a chat either, so the disagreement is not
user-visible, which is exactly why the overlay-only carry was preferred over the proto field. The
authoritative closure is the `title` field on `GetSessionMessages` the entry above named (the same
read path the reasoning-persistence entry independently wants widened), dead until a consumer that
opens an out-of-window chat beside the switcher exists (toast activation routing once
`NotifyRequest` carries a `session_id`, or a search / deep-link by id).
**Narrowed 2026-08-03 without being closed.** With the two `TITLE_MAX` declarations now equal
(the addendum recorded above), the local derivation renders exactly what the brain would have
listed for the same first message, so the fallback no longer differs in *length*. What is still
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
