# One pair of run bounds reaches every roster entry and the entries convert between them differently

**Status:** declined 2026-09-11
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-29 by the close of
[R-478](478-two-ceilings-on-one-run-and-no-ordering.md), whose decision is that the cap and the run
deadline are independent bounds and that converting between them is the operator's own work, done
at the tier's decode rate.

That decision hands the operator a conversion that is **per tier**, and the config gives them one
pair of numbers for the whole roster. `SubagentsConfig.attempt_bounds` builds a single
`AttemptBounds` from the flat `max_tokens` and `run_timeout_s`; `build_subagents` hands that one
value to the one `SubagentRunner`, which holds one `PlacedAttempt`, so every entry runs under it.
`SubagentRosterEntry` carries an endpoint, a GPU endpoint, the three resource asks and a
description, and no bounds at all, though the asks are the precedent for adding some: each defaults
off the flat field's own module constant. The rates those bounds convert at are already not one
number across the entries this repo ships. The delegation runbook reads gemma-4-E4B at 0.18 to 1.35
tok/s and Qwen3.5-2B at about 1 tok/s, and a GPU placement is a different number again on both.

**The rates are already far apart, and the widest gap is inside one entry rather than between two.**
The GPU-placed subagent tier was measured on 2026-08-04 at 96.96 tok/s generating alone and 63.50
beside a generating cortex, against the CPU entry's 0.18 to 1.35. That tier serves the artifact
`CORTEX_MODEL_FILE_SUBAGENT` names, so those two readings are the same model on the two placements
one `SubagentRosterEntry` already carries, `endpoint` and `gpu_endpoint`. Bounds added to the entry
the way the resource asks were would therefore still hand both placements one conversion, and the
factor between them is about fifty to five hundred where the factor between the two CPU entries is
about one.

**Why it was left.** Nothing shipped is hurt yet, and the reason offered was that the measured rates
overlap: the roster alternate's roughly 1 tok/s sits inside the default entry's own interval, so one
pair covers both about as well as it covers either. That holds for the two CPU entries and not for
the placement above. The cost is also not the two JSON fields it
looks like. Three boot checks are written against **one** deadline, and each would have to become a
check per entry: the deadline against the stall ceiling, which is one ceiling because every entry
shares one generation client; the hold against the admission wait, which is one wait because every
entry queues on one `ResourceBudgetScheduler`; and the deadline against a whole delegated dispatch,
which is one tool configuration. Per-entry deadlines would make the second of those a relation
between one entry's hold and a wait every other entry is queued behind, which is a different and
harder claim than the one that check makes today. This is the same shape as
[R-482](482-the-sentence-is-one-wording-for-every-entry.md), one flat setting applied to a roster
whose entries do not agree about it, and the two would be worth reading together.

**What would close it.** Decide where a bound belongs now that the widest gap is known to be a
placement's rather than an entry's. Putting `max_tokens` and `run_timeout_s` on
`SubagentRosterEntry`, defaulting off the flat fields the way the resource asks already do, covers
a roster of CPU entries and says nothing about the GPU arm, so a per-placement pair is the shape
the readings argue for and is the more expensive of the two. Either way the three orderings need an
answer for a roster carrying several deadlines: most likely the longest, since the wait and the
dispatch bound are pool-wide. The one reading still missing is the CPU alternate's rate on the
bodies and shapes the ceilings table was read on, which is the measurement that says whether the
two CPU entries can keep sharing a pair once the placement no longer can.

## Trail

- 2026-08-29: opened by the close of
  [R-478](478-two-ceilings-on-one-run-and-no-ordering.md), which declared the cap and the run
  deadline independent and left the conversion between them to the operator, at a decode rate that
  is the entry's own while the pair of bounds is the deployment's.
- 2026-09-09: **The trigger had fired 25 days before this entry was opened.** It named the
  GPU-placed subagent bring-up as one of the two readings that would fire it, and that bring-up
  closed on 2026-08-04 having measured the GPU tier at 96.96 and 63.50 tok/s against the CPU
  entry's 0.18 to 1.35, recorded in the resource-governance fit test and in the GPU runbook's
  measured table. So the entry was filed waiting for a number the repo already held. The correction
  the number carries is that the gap is between two placements of one entry rather than between two
  entries, which is why the fix this entry proposed would not reach it. Everything else holds:
  `attempt_bounds` still builds one `AttemptBounds` from the flat `max_tokens` and `run_timeout_s`,
  `build_subagents` still hands it to the one `SubagentRunner` holding one `PlacedAttempt`,
  `SubagentRosterEntry` still carries no bounds, and the three checks written against one deadline
  are still the two validators in `config_subagents.py` and the dispatch ordering in `bounds.py`.
- 2026-09-11: **Declined. The pair is one bound per regime, and a placement changes which of the
  two binds and never what either is sized to.** Re-derived first: `attempt_bounds` still builds one
  `AttemptBounds`, `build_subagents` still hands it to the one `SubagentRunner` and its one
  `PlacedAttempt`, `SubagentRosterEntry` and `SubagentProfile` still carry no bounds, every entry
  still shares the one generation client and its stall ceiling, and the three orderings are still
  the two validators in `config_subagents.py` and `check_tool_call_deadline` in `bounds.py`. The gap
  this entry found is real and is the pair doing what its own docstring says: the cap binds a fast
  tier and the deadline a slow one. The cap is sized from the reply, which is the model's and not
  the placement's (the E4B at `-ngl 99` wrote replies of 250 to 373 decoded tokens today, the band
  the ceilings table read), and the deadline from the slow placement's whole subtask. On the GPU
  placement the whole cap decodes in 7 to 9 s (1024 tokens at 115 to 148 tok/s; today's one capped
  run took 7.6 s of wall clock) and a deadline of its own could not be set under the 600 s stall
  ceiling every entry shares, so no decoding there can reach any deadline the validators accept,
  and what the deadline bounds on that placement is tool dispatches, which the dispatch ordering
  already holds. A per-placement cap would be the same number by construction. The two CPU entries
  share a pair on this entry's own reading, the alternate's rate sitting inside the default's
  interval, and the instruction addendum read the cap margin on the alternate and on E2B with no
  reply past 721 tokens on either. So bounds per entry or per placement would add three orderings
  per entry against pool-wide partners and change nothing a run is held to. What would reopen it: a
  roster entry whose measured longest reply on the shipped shape exceeds the flat cap, or a CPU
  entry whose slow-end rate under the flat deadline admits fewer tokens than its own longest reply,
  which is the ceilings table's arithmetic taken per entry. Recorded in the ADR-0005 roster-bounds
  addendum, with a sentence in both module contracts and the delegation runbook.
