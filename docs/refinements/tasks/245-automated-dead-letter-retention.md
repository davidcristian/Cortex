# Automated dead-letter retention

**Status:** declined 2026-08-18
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded inside the dead-letter inspection entry, which landed the operator-facing
`dead_letters()` / `purge_dead_letter()` pair on the Redis schedule store and its runbook recipe,
and left automated retention deferred until quarantine volume ever existed.

**Declined, on three findings, none of which needs a live observation.**

**The hash cannot grow the way the deferral describes.** `quarantine` writes the raw bytes under the
item id and, in the same transaction, removes that id from the due, firing and deliverable sets and
deletes the record
([schedule_claims.py](../../../brain/packages/session/src/cortex_session/schedule_claims.py)), so a
quarantined item can never be claimed again, and ids are uuid4, so a second quarantine of the same
item overwrites its own field rather than adding one. The ceiling is therefore the number of
distinct schedules this single user ever created that then also failed to decode. There is no loop
that can pump it, and "volume" here would mean hundreds of personally created schedules corrupting,
at which point the corruption is the incident and the hash is the evidence.

**Expiry would delete the only record of the only exceptional event on this path.** The value kept
is exactly the bytes the codec refused, rendered with replacement characters rather than decoded a
second time, and it is the whole forensic trail. After a retention window an operator cannot tell
"nothing ever corrupted" from "something did and the evidence timed out", which is strictly worse
than a hash that grows by one entry and logs loudly when it does.

**And a sweep cannot reach these calls without breaking the ports rule.** The ticker holds the
`ScheduleStore` port, and the port deliberately carries no dead-letter method: the origin decision
put both verbs on the adapter because quarantine is a codec mechanic of the Redis claim path that
the in-memory fake can never produce, so a port method would force a vacuous fake. An automated
policy driven from the ticker therefore needs either that vacuous method or the concrete adapter
injected into the orchestrator.

**The shape a reversal would take, recorded so nobody re-derives it.** It is not a sweep at all: it
is one `hexpire` on the field beside the `hset` in `quarantine`, adapter-local and transactional
with it. Both sides of the gate can run it, the compose stack pinning `redis:8-alpine` and the
`fakeredis` in this workspace answering `hexpire` when it was tried on 2026-08-18. So the reason
this is closed is the policy, not the cost.

## Trail

- 2026-07-12: Recorded as the remainder when dead-letter inspection landed.
- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket this entry sits in ran against
  the tree and fired nothing.
- 2026-08-18: Declined on a re-derivation. Growth is one field per corrupt item id with the item
  removed from every live index in the same transaction, so the trigger has no producer; automated
  expiry would erase the distinction between a clean history and a lost one; and the port has no
  dead-letter verb by an argued decision, so the implicit "just add a sweep" would break the ports
  rule. The runbook's closing sentence about the ledger was reworded in the same change, and the
  reasoning is recorded at the origin decision.
