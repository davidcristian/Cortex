# The shipped ordering of two bounds is checked at boot and not in the repo

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** A retune of `DEFAULT_TOOL_CALL_TIMEOUT_S` or `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` that
inverts the shipped pair, which nothing would catch until a deployment turned both tools and
delegation on. Neither number has moved since it was declared.

`check_tool_call_deadline` refuses a **deployment** whose delegated dispatch does not fit under its
run bound. It reads two `pydantic-settings` classes, so what it holds is whatever env this process
was given, and it holds nothing about the numbers this repo ships:
`DEFAULT_TOOL_CALL_TIMEOUT_S = 60.0` in `cortex_core/tool_deadline.py` and
`DEFAULT_SUBAGENT_RUN_TIMEOUT_S = 2400.0` in `cortex_core/subagents.py` could be retuned into an
inverted pair, and every suite would stay green because the check runs only with both capabilities
enabled, which CI never does.

Note that the relation the scan would hold is not quite the one the check makes. The check
compares the run bound against a **multiple** of the call bound, `delegated_call_bounds`, since one
dispatch spends the bound once per registry walk and the walk count depends on how many sidecars a
deployment configures. The repo's own pair has no sidecar count, so what a registry row could hold
is the weakest form of the relation, the shipped call bound under the shipped run bound, which is
the ordering below and not the whole of the check. That is still worth having: it is the form the
two numbers can be compared in without a deployment, and a retune that inverts even that is
certainly wrong.

The gate for exactly this already exists and does not reach. `scripts/crosscheck.py` has
`Relation.ORDERED` for bounds that must sit under one another rather than match, and two seam
couplings use it. It cannot hold this pair for two reasons, both in `values.py`:

- **It compares integers only.** `relation_fault` filters the readings to `isinstance(value, int)`
  and reports "an ordering compares integers, and a site here declares something else" when any
  reading is not one. Both of these bounds are floats, as are the stall ceiling and the admission
  wait beside them, so no bound on this tier can be registered as an ordering today.
- **It is non-decreasing, not strict.** `all(lower <= upper ...)` admits equality, and every
  ordering between these bounds is strict, equality being the race the boot checks refuse.

So this is one entry with two halves: widen the relation to any number the reducer produces, and
give it a strict variant (or a second `Relation`) for the bounds whose orderings are strict. Then
the shipped pair, and the run deadline against the stall ceiling beside it, become registry rows
rather than facts held only by a deployment that happens to enable both capabilities.

Both numbers are registered as ordinary equalities already, each tied to the runbooks and module
contracts that restate it, so what is missing is only the relation **between** them. That is also
why the gap is narrow: a retune of either number alone still fails the scan unless every document
moves with it, and what nothing catches is a retune where every document does move and the pair
ends up the wrong way round.

## Trail

- 2026-08-21: Filed by the close of
  [363](363-the-call-bound-and-the-run-bound-are-unordered.md), which ordered the pair for a
  deployment and left the repo's own copy of it ungated. Recorded in the ADR-0009 ordering
  addendum.
