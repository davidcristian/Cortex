# The shipped ordering of two bounds is checked at boot and not in the repo

**Status:** satisfied 2026-09-19
**Area:** repo-checks
**Origin:** [ADR-0047](../../adr/ADR-0047-delegated-run-bound-ordering.md)

`check_tool_call_deadline` refuses a deployment whose delegated dispatch does not fit under its run
bound. It reads two `pydantic-settings` classes, so what it compares is whatever environment this
process was given, and it says nothing about the numbers this repo ships:
`DEFAULT_TOOL_CALL_TIMEOUT_S = 60.0` in `cortex_core/tool_deadline.py` and
`DEFAULT_SUBAGENT_RUN_TIMEOUT_S = 2400.0` in `cortex_core/subagents.py` could be retuned into an
inverted pair, and, this entry assumed, every suite would keep passing.

The relation a registry row could check is weaker than the one the boot check makes. The check
compares the run bound against a multiple of the call bound, `delegated_call_bounds`, since one
dispatch uses the bound once per registry walk and the walk count depends on how many sidecars a
deployment configures. The repo's own pair has no sidecar count, so a row could only compare the
shipped call bound against the shipped run bound.

`scripts/crosscheck.py` has `Relation.ORDERED` for bounds that must sit under one another, and it
cannot cover this pair for two reasons, both in `relation_fault`, which was in `values.py` when
this was filed and now lives in `scripts/readings.py`:

- It compares integers only. `relation_fault` filters the readings to `isinstance(value, int)` and
  reports "an ordering compares integers, and a site here declares something else" when any reading
  is not one. Both bounds are floats, as are the stall ceiling and the admission wait beside them.
- It is non-decreasing, not strict. `all(lower <= upper ...)` admits equality, and every ordering
  between these bounds is strict, equality being the race the boot checks refuse.

## History

- 2026-08-21: Filed by the close of
  [363](363-the-call-bound-and-the-run-bound-are-unordered.md), which ordered the pair for a
  deployment and left the repo's own copy of it unchecked. Recorded in ADR-0047 decision 3.
- 2026-08-23: Widened by the decline of
  [407](407-three-held-bounds-and-an-unheld-ordering.md), which proposed the same widening for the
  three subagent bounds and was refused because a settings class already refuses both of those
  orderings for any deployment and for the repo's own numbers. The decline also measured the
  non-strictness above: `relation_fault` returns None on three equal readings, so the two halves
  here are needed together.
- 2026-09-07: Checked and left open. Neither number has moved:
  `git log -L64,64:brain/packages/core/src/cortex_core/tool_deadline.py` and
  `git log -L149,149:brain/packages/core/src/cortex_core/subagents.py` each return exactly one
  commit, the one that declared the line. Both halves of the widening are still unbuilt. The
  entry's pointer to `values.py` was stale and is repaired above: that function moved to
  `readings.py` when `values.py` reached the line cap.
- 2026-09-13: Checked again and left open. `DEFAULT_TOOL_CALL_TIMEOUT_S` is still 60.0 at
  `tool_deadline.py:64` and `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` still 2400.0 in `subagents.py`, where
  the declaration has moved to line 152 from the 149 cited above; `git log -L` on each line returns
  exactly one commit. `relation_fault` in `scripts/readings.py` still filters its readings to
  `isinstance(value, int)` and still compares with `all(lower <= upper for lower, upper in
  pairwise(numbers))`. The only two registered orderings are still the pair of `Relation.ORDERED`
  entries in `scripts/wirecouplings.py`.
- 2026-09-19: Satisfied. The premise was false the day the entry was filed: the commit that filed
  it also added `test_the_shipped_pair_is_wired_and_says_so` and
  `test_a_second_sidecar_costs_the_same_bound_more` to
  `brain/packages/orchestrator/tests/test_bounds.py`, which run `check_tool_call_deadline` with
  both capabilities on and the two shipped defaults imported rather than retyped, on every commit.
  Both settings classes declare those constants as their field defaults, so the pair compared is
  the pair a deployment gets, and an inverted one raises `ToolCallDeadlineError` there. They check
  more than a registry row could: the whole dispatch, three call bounds at one sidecar and seven at
  two, strictly under the run bound. The row this entry proposed could not have been registered
  either: both declarations are in `cortex_core`, an ordering may have no mentions, and
  `test_every_registered_constant_spans_more_than_one_boundary_side` refuses an entry whose places are
  all Python in one brain package. Measured on a copy of the tree over the whole brain workspace
  suite (3320 passing): the call bound retuned to 3000.0, or to 900.0, which the bare ordering
  admits, fails exactly those two cases by the check's own refusal, and the run bound retuned to
  50.0 fails 38 cases at the stall-ceiling validator before the pair is compared. No widening was
  built, since nothing is left to use it: the subagent trio is covered by `SubagentsConfig`
  validators ([407](407-three-held-bounds-and-an-unheld-ordering.md)), this pair by the suite, and
  the two registered orderings are integers. Recorded in ADR-0047 decision 7. Opens nothing.
