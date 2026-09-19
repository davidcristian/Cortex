# Automated dead-letter retention

**Status:** declined 2026-08-18
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded inside the dead-letter inspection entry, which added the operator-facing `dead_letters()`
and `purge_dead_letter()` pair on the Redis schedule store and left automated retention deferred
until there was ever any quarantine volume.

Declined, on three findings, none of which needs a live observation:

- The hash cannot grow the way the deferral describes. `quarantine` writes the raw bytes under the
  item id and, in the same transaction, removes that id from the due, firing and deliverable sets
  and deletes the record
  ([schedule_claims.py](../../../brain/packages/session/src/cortex_session/schedule_claims.py)), so
  a quarantined item can never be claimed again, and ids are uuid4, so a second quarantine of the
  same item overwrites its own field. The maximum is therefore the number of distinct schedules
  this one user ever created that then failed to decode. Nothing can pump it, and "volume" would
  mean hundreds of hand-created schedules corrupting, at which point the corruption is the incident
  and the hash is the evidence.
- Expiry would delete the only record of the only exceptional event on this path. The value kept is
  exactly the bytes the codec refused, rendered with replacement characters rather than decoded
  again, and it is the whole forensic trail. After a retention window an operator cannot tell
  "nothing ever corrupted" from "something did and the evidence expired", which is worse than a
  hash that grows by one entry and logs loudly when it does.
- A periodic cleanup cannot reach these calls without breaking the ports rule. The ticker has the
  `ScheduleStore` port, and the port deliberately has no dead-letter method, so an automated policy
  driven from the ticker needs either an empty fake method or the concrete adapter injected into
  the orchestrator.

If this is ever reversed, the shape is not a periodic cleanup: it is one `hexpire` on the field
beside the `hset` in `quarantine`, local to the adapter and in the same transaction. Both sides can
run it, since the compose stack uses `redis:8-alpine` and the `fakeredis` in this workspace
implemented `hexpire` when it was tried on 2026-08-18. The reason this is closed is the policy, not
the cost.

## History

- 2026-07-12: Recorded as the remainder when dead-letter inspection was added.
- 2026-08-09: A review of the entries deferred until they cause a problem found that none had.
- 2026-08-18: Declined, on the findings above. The runbook's closing sentence about the log was
  reworded in the same change, and the reasoning is recorded at the origin decision.
