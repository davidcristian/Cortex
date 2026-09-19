# Authoritative title for a chat outside the loaded window

**Status:** open, waiting for a consumer
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Trigger:** A second caller that opens a chat by id from outside the loaded window, beside the reminder card's open control, such as toast activation routing once `NotifyRequest` has a `session_id` (R-230) or a search.
**Verified:** 2026-09-19

`headerTitle` reads the title from `state.sessions`, so a chat that is not in the loaded recency
window still derives its header locally. The only path today that opens such a chat is a reminder
deep-link (`Reminders.tsx` "open chat"), and the switcher shows no row for it either, so the
disagreement is not visible to the user. That is why the overlay-only fix in
[179](179-open-chat-header-title.md) was preferred over a proto field.

The authoritative fix is a `title` field on `GetSessionMessages`, which is dead work until a second
caller opens a chat from outside the window.

With the two `TITLE_MAX` declarations now equal and checked against each other by
`scripts/crosscheck.py`, the local derivation renders exactly what the brain would have listed for
the same first message, so the fallback no longer differs in length. What it still cannot know is a
user rename or a generated title stored against that chat.

## History

- 2026-07-16: Opened behind the overlay-only header-title fix.
- 2026-08-03: Narrowed without closing, once the two `TITLE_MAX` declarations were equal.
- 2026-09-13: Checked against the tree and still true. `headerTitle` still falls back to `titleFor`
  (`body/app/src/overlay/sessionState.ts`), `GetSessionMessagesReply` still has messages and no
  title (`proto/body.proto`), and the catalog still loads 50 rows (`SESSION_LIST_LIMIT`,
  `body/app/src/overlay/useSessionCatalog.ts`). The trigger has not fired.
- 2026-09-19: Checked again; every code claim from 2026-09-13 holds, and `Reminders.tsx` is still
  the only caller of `onSelectSession` with an id the loaded list may not have. Two things were
  wrong. The trigger's last example, "a deep-link by id", was already met when it was written, since
  the reminder card's open control is one, so the trigger now asks for a second caller. And
  [118](118-reasoning-thinking-status.md) does not want this read path widened: its reasoning
  re-display was declined on 2026-07-16 for want of a consumer. The trigger has not fired:
  [230](230-toast-activation-routing.md) is still dead, `NotifyRequest` has no `session_id`, and no
  search exists.
