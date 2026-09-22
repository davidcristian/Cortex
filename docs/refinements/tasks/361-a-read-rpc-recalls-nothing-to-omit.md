# A session read has no recalled context, so there is no partial answer to give

**Status:** open, waiting for a consumer
**Area:** rpc-transport
**Origin:** [ADR-0061](../../adr/ADR-0061-abandoned-call-line.md)
**Verified:** 2026-09-19
**Trigger:** A read RPC on `BrainService` that recalls anything at all, meaning a handler that
reads a memory port and composes what it finds into its reply. Today none does, so there is
nothing for a reply to be partial about.

The change asked for was a session read whose memory cascade will not fit returning the transcript
without it, and a field on the wire saying so, because a transcript missing its recalled context
with nothing declaring the omission cannot be told from a session that recalled nothing.

The mechanism it describes is not in the tree. `GetSessionMessages` calls `SessionStore.history`
and maps the result; it touches no memory port. `SessionMemoryCascade` reaches exactly one handler,
`DeleteSession`, where it is a write and not a read, and where the ordering is already a deliberate
decision in the other direction: the session is hard-deleted first, so a memory failure leaves the
chat gone with a retry cleaning up, rather than leaving a visible chat whose memories vanished.

The recall this is really about happens inside a turn, where `MemoryRecaller` composes what it
finds into the prompt. `Converse` announces no deadline, so there is no reading there to decide
anything from.

So the change is not declined on its merits; it has no site. Should a read RPC ever gain a recall
step, the wire question is real: an omission a reader cannot see is worse than a refusal, and the
reply has one free-text `detail`, which [320](320-one-detail-string-two-facts.md) already records
as one sentence doing the work of two facts.

## History

- 2026-08-21: Filed by the close of [341](341-nothing-declines-work-it-cannot-finish.md), which
  found that this one of its three shapes describes a cascade no read path has.
- 2026-09-13: Checked again, unchanged, and the trigger has not fired. `session_servicer.py` has
  all five session RPCs and every one of them calls the store alone: `GetSessionMessages` is
  `self._store.history(...)` mapped, and `SessionMemoryCascade` is still injected for
  `DeleteSession` only.
- 2026-09-19: Checked again, and the trigger has not fired, but the last entry miscounted the
  service. `BrainService` declares eleven RPCs ([proto/body.proto](../../../proto/body.proto)):
  `Converse` and ten others. Five of those read: `Health`, `ListSessions`, `GetSessionMessages`,
  `ListDueReminders` and `GetPreferences`. The other five write: `RenameSession`, `DeleteSession`,
  `SetSessionHoisted`, `AckReminder` and `SetPreference`. The last entry called `AckReminder` and
  `SetPreference` reads and left `Health` out. None of the five reads touches a memory port:
  `GetSessionMessages` is still `self._store.history(...)` mapped (`session_servicer.py`),
  `ListDueReminders` reads the `ScheduleStore`, `GetPreferences` the preference store, and `Health`
  the `ResidencyReporter` (`server.py`). `SessionMemoryCascade` is still injected for
  `DeleteSession` alone.
