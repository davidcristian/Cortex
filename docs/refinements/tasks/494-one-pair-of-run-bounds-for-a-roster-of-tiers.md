# One pair of run bounds reaches every roster entry and the entries convert between them differently

**Status:** declined 2026-09-11
**Area:** subagents
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

[R-478](478-two-ceilings-on-one-run-and-no-ordering.md) decided that the token cap and the run
deadline are independent and that converting between them is the operator's work, done at the tier's
decode rate. That conversion is per tier, and the config gives one pair of numbers for the whole
roster. `SubagentsConfig.attempt_bounds` builds a single `AttemptBounds` from the flat `max_tokens`
and `run_timeout_s`; `build_subagents` hands that one value to the one `SubagentRunner`, which holds
one `PlacedAttempt`, so every entry runs under it. `SubagentRosterEntry` has an endpoint, a GPU
endpoint, the three resource requests and a description, and no bounds.

The rates are already far apart, and the widest gap is inside one entry rather than between two. The
GPU-placed subagent tier was measured on 2026-08-04 at 96.96 tok/s generating alone and 63.50 beside
a generating cortex, against the CPU entry's 0.18 to 1.35. Those two readings are the same model on
the two placements one `SubagentRosterEntry` already has, `endpoint` and `gpu_endpoint`.

## History

- 2026-08-29: opened by the close of
  [R-478](478-two-ceilings-on-one-run-and-no-ordering.md), which declared the cap and the run
  deadline independent and left the conversion to the operator, at a decode rate that is the entry's
  own while the pair of bounds is the deployment's.
- 2026-09-09: the trigger had fired 25 days before this entry was opened. It named the GPU-placed
  subagent bring-up as one of the two readings that would fire it, and that bring-up closed on
  2026-08-04 having measured the GPU tier at 96.96 and 63.50 tok/s against the CPU entry's 0.18 to
  1.35. So the entry was filed waiting for a number the repo already had, and the gap is between two
  placements of one entry rather than between two entries. Everything else holds.
- 2026-09-11: declined. The pair is one bound per regime, and a placement changes which of the two
  binds and never what either is sized to. Checked again first: `attempt_bounds` still builds one
  `AttemptBounds`, `build_subagents` still hands it to the one `SubagentRunner`,
  `SubagentRosterEntry` and `SubagentProfile` still have no bounds, every entry still shares the one
  generation client and its stall limit, and the three orderings are still the two validators in
  `config_subagents.py` and `check_tool_call_deadline` in `bounds.py`. The cap is sized from the
  reply, which is the model's and not the placement's (the E4B at `-ngl 99` wrote replies of 250 to
  373 decoded tokens, the band the limits table read), and the deadline from the slow placement's
  whole subtask. On the GPU placement the whole cap decodes in 7 to 9 s (1024 tokens at 115 to 148
  tok/s) and a deadline of its own could not be set under the 600 s stall limit every entry shares,
  so no decoding there can reach any deadline the validators accept, and what the deadline bounds on
  that placement is tool dispatches, which the dispatch ordering already covers. The two CPU entries
  share a pair on this entry's own reading, the alternate's rate falling inside the default's
  interval. So bounds per entry or per placement would add three orderings per entry against
  pool-wide partners and change nothing a run is limited by. What would reopen it: a roster entry
  whose measured longest reply on the shipped shape exceeds the flat cap, or a CPU entry whose
  slow-end rate under the flat deadline admits fewer tokens than its own longest reply. Recorded in
  ADR-0048, with a sentence in both module contracts and the delegation runbook.
