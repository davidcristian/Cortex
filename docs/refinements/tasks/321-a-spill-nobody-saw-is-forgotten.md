# A spill nobody was awake for is forgotten by design

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Trigger:** an operator asks whether a slow deep task has happened before, or a second per handoff
verdict arrives that is worth counting rather than displaying. The failed handoff's reason arrived
three days after this entry was opened and is not one of those: it was decided on 2026-09-15 as
neither counted nor displayed, and R-379 closed on that. Checking the counting half is one reading: nothing in the brain keeps a per handoff row that
outlives its handoff, `HandoffSettler._settle` deleting a `DONE` record outright and the Redis
adapter expiring a `FAILED` one after an hour, so a count still has nowhere to live.
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-15

Opened 2026-08-19 by the close of [304](304-spill-rides-the-residency-report.md). The standing rule
that close chose is deliberate and it has a price: the note lives in the process, stands for an
hour, and is cleared by the next handoff that holds its pace, so a handoff that spilled at 03:00 is
gone by morning and a brain that restarted takes it with it. What an operator can read is therefore
only ever "the last handoff", never "this has happened four times this week", and the log is the
only place the history exists at all: one `WARNING` per spilled handoff, written by the deep phase
([brain_phase.py](../../../brain/packages/core/src/cortex_core/brain_phase.py)) with the observed
rate, the floor and the shortfall in fields. The note's own lifetime is decided in
[residency_pace.py](../../../brain/packages/core/src/cortex_core/residency_pace.py), which logs
nothing.

That was the right trade for a display surface, since a report about **now** must not be
answered with a fact about last Tuesday. It is the wrong trade for a question about a pattern, and
the two need different homes: a count of spilled handoffs is durable data, not a tooltip, so
closing this means deciding where such a per handoff verdict is kept and what reads it, rather than
lengthening the note. Nothing about the current note changes either way.

**The home this entry first nominated is not available, re-derived on 2026-09-08.** The original
text offered the handoff record, on the grounds that it survives a swap and is written once per
handoff. Both of those are true and neither makes it a home for a count, because the record does
not survive the handoff. `HandoffSettler._settle`
([swap_settle.py](../../../brain/packages/core/src/cortex_core/swap_settle.py)) deletes the record
on `DONE`, that delete being what frees the store's active pointer, and a spilled handoff is a
successful one: the card was overcommitted, both tiers reported ready, and only the decode rate was
wrong. So the handoffs a spill count would count are exactly the ones that leave nothing behind. A
record settled `FAILED` is kept instead, under the `_TERMINAL_TTL_SECONDS` of 3600 seconds in
[handoffs.py](../../../brain/packages/session/src/cortex_session/handoffs.py), which is the same
hour `DEFAULT_SPILL_DWELL_S` gives the note. Nothing in the brain writes a per handoff row that
outlives its handoff, so closing this means choosing a store as well as a shape. This is where the
entry touches the rule that state must survive a model swap, and the two obligations are not one:
the record exists so that a turn outlives the swap, and it is released as soon as the turn it
carried is finished, which is why a store built for swap survival is not a store for history.

**A second per handoff verdict has arrived, and it is not one of the counting kind.** Three days
after this entry was opened, a handoff settled `FAILED` gained a reason, written onto the record and
into one `WARNING` from the settler. That is this shape one step further along, and on 2026-09-15
its own entry, [R-379](379-a-settled-reason-nothing-reads-back.md), was declined: the reason keeps
the log line and the record and gains no surface, because the residency report only annotates a
serving answer and would therefore be silent on the two states whose reason is worth having. So the
trigger's second half has been approached once and settled against counting as firmly as against
displaying, which leaves this entry's own subject, a spill, the only per handoff verdict here that
anybody has argued is worth a history.

## Trail

- 2026-08-19: Opened by the close of [304](304-spill-rides-the-residency-report.md), which argued
  the dwell from the two lifetimes a spill has and recorded, rather than smuggled, the history that
  choosing an hour throws away.
- 2026-09-08: trigger checked and not fired, and the nominated home was found unavailable. The
  readings: the spill's only history is one `WARNING` in `brain_phase.py`, not in
  `residency_pace.py`, which holds no logger; `HandoffSettler._settle` deletes a `DONE` record, so a
  successful handoff leaves none; `_TERMINAL_TTL_SECONDS` is 3600 and `DEFAULT_SPILL_DWELL_S` is
  3600.0, chosen three days apart by two decisions that did not cite each other; and the one later
  verdict of this shape, the failed handoff's reason, is a display question rather than a counting
  one.
- 2026-09-09: claims held to the code and all of them stand. `HandoffSettler._settle` still deletes
  a `DONE` record, `_TERMINAL_TTL_SECONDS` is still 3600 and `DEFAULT_SPILL_DWELL_S` still 3600.0,
  the spill's only history is still the one `WARNING` in `brain_phase.py`, and `residency_pace.py`
  still binds no logger. Recorded above: why the record's swap survival is not the durability a
  count would need. The trigger has not fired.
- 2026-09-13: claims held to the code again and all of them stand. `HandoffSettler._settle` still
  deletes a `DONE` record, `_TERMINAL_TTL_SECONDS` is still 3600 and `DEFAULT_SPILL_DWELL_S` still
  3600.0, the spill's only history is still the one `WARNING` in `brain_phase.py`, and
  `residency_pace.py` still binds no logger. One reading sharpens which handoffs this would count:
  `swap_in` ([residency_moves.py](../../../brain/packages/core/src/cortex_core/residency_moves.py))
  stops the cortex under every plan, a co-resident plan sparing only the standing peers, so the
  pair that overcommits the card is the deep tier and a peer rather than the deep tier and the
  cortex. The trigger has not fired.
- 2026-09-15: claims held to the code again and all of them stand. `HandoffSettler._settle` still
  deletes a `DONE` record, `_TERMINAL_TTL_SECONDS` is still 3600 and `DEFAULT_SPILL_DWELL_S` still
  3600.0, the spill's only history is still the one `WARNING` in `brain_phase.py`, and
  `residency_pace.py` still binds no logger. The trigger's second half moved and is recorded above:
  the failed handoff's reason was decided against a surface as well as against a count, so no
  second verdict of the counting kind has arrived and this entry is still the only one arguing for
  a per handoff row. Choosing a store and a shape is still what closing it costs, and the one hard
  rule points at Postgres rather than at the record, since a record built for swap survival is
  released the moment the turn it carried is finished. The trigger has not fired.
