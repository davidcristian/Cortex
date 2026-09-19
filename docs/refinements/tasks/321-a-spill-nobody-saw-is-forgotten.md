# A spill nobody was awake for is forgotten by design

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Trigger:** an operator asks whether a slow deep task has happened before, or a second per handoff
result arrives that is worth counting rather than displaying. The failed handoff's reason arrived
three days after this entry was opened and is not one of those: it was decided on 2026-09-15 as
neither counted nor displayed, and R-379 closed on that. Checking the counting half is one reading:
nothing in the brain keeps a per handoff row that outlives its handoff, `HandoffSettler._settle`
deleting a `DONE` record outright and the Redis adapter expiring a `FAILED` one after an hour, so a
count still has nowhere to live.
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)
**Verified:** 2026-09-19

The spill note lives in the process, lasts an hour, and is cleared by the next handoff that keeps
its pace, so a handoff that spilled at 03:00 is gone by morning and a brain that restarted takes it
with it. An operator can read "the last handoff" and never "this has happened four times this
week". The log is the only place the history exists: one `WARNING` per spilled handoff, written by
the deep phase ([brain_phase.py](../../../brain/packages/core/src/cortex_core/brain_phase.py)) with
the observed rate, the floor and the shortfall as fields. The note's own lifetime is decided in
[residency_pace.py](../../../brain/packages/core/src/cortex_core/residency_pace.py), which logs
nothing.

That is the right trade for a display, since a report about now must not answer with a fact about
last Tuesday. It is the wrong trade for a question about a pattern. A count of spilled handoffs is
durable data, not a tooltip, so closing this means deciding where such a record is kept and what
reads it, rather than making the note last longer.

The home this entry first proposed is not available. The handoff record survives a swap and is
written once per handoff, and neither makes it a home for a count, because the record does not
survive the handoff. `HandoffSettler._settle`
([swap_settle.py](../../../brain/packages/core/src/cortex_core/swap_settle.py)) deletes the record
on `DONE`, that delete being what frees the store's active pointer, and a spilled handoff is a
successful one: the card was overcommitted, both tiers reported ready, and only the decode rate was
wrong. So the handoffs a spill count would count are exactly the ones that leave nothing behind. A
record settled `FAILED` is kept instead, under the `_TERMINAL_TTL_SECONDS` of 3600 seconds in
[handoffs.py](../../../brain/packages/session/src/cortex_session/handoffs.py), the same hour
`DEFAULT_SPILL_DWELL_S` gives the note. The rule that state must survive a model swap does not help
here: the record exists so that a turn outlives the swap, and it is released as soon as that turn
is finished, so a store built for swap survival is not a store for history.

## History

- 2026-08-19: Opened by the close of [304](304-spill-rides-the-residency-report.md), which argued
  the dwell from the two lifetimes a spill has and recorded the history that choosing an hour
  throws away.
- 2026-09-08: Trigger checked and not fired, and the proposed home found unavailable. The readings:
  the spill's only history is one `WARNING` in `brain_phase.py`, not in `residency_pace.py`, which
  has no logger; `HandoffSettler._settle` deletes a `DONE` record, so a successful handoff leaves
  none; `_TERMINAL_TTL_SECONDS` is 3600 and `DEFAULT_SPILL_DWELL_S` is 3600.0, chosen three days
  apart by two decisions that did not cite each other; and the one later result of this kind, the
  failed handoff's reason, is a display question rather than a counting one.
- 2026-09-09: Claims checked against the code and all stand. `HandoffSettler._settle` still deletes
  a `DONE` record, `_TERMINAL_TTL_SECONDS` is still 3600 and `DEFAULT_SPILL_DWELL_S` still 3600.0,
  the spill's only history is still the one `WARNING` in `brain_phase.py`, and `residency_pace.py`
  still has no logger. The trigger has not fired.
- 2026-09-13: Claims checked again and all stand, with the same four readings. One reading sharpens
  which handoffs this would count: `swap_in`
  ([residency_moves.py](../../../brain/packages/core/src/cortex_core/residency_moves.py)) stops the
  cortex under every plan, a co-resident plan sparing only the permanent peers, so the pair that
  overcommits the card is the deep tier and a peer rather than the deep tier and the cortex. The
  trigger has not fired.
- 2026-09-15: Claims checked again and all stand. The trigger's second half moved: the failed
  handoff's reason was decided against a display as well as against a count, so no second result of
  the counting kind has arrived and this entry is still the only one arguing for a per handoff row.
  The trigger has not fired.
- 2026-09-19: Claims checked again and all stand. `HandoffSettler._settle` still writes the
  terminal state and then deletes a `DONE` record through `_release_claim`, `_TERMINAL_TTL_SECONDS`
  is still 3600 and `DEFAULT_SPILL_DWELL_S` still 3600.0, the spill's only history is still the one
  `WARNING` in `brain_phase.py`, and `residency_pace.py` still has no logger. That `WARNING`'s rate
  fields were renamed on 2026-09-17 to `decode_rate`, `decoded` and `floor_rate`, because the log
  formatter had been printing them as `<redacted>`, so the observed rate and the floor are readable
  only since then. No second per handoff result has arrived. The trigger has not fired.
