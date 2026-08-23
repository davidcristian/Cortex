# Three bounds are held as three values and the ordering they are stated in is held by nothing

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-23 by the close of
[R-402](402-the-stall-ceiling-is-ordered-against-two-held-bounds.md), which registered the last of
the three numbers and made the gap visible by closing the others.

`brain/packages/core/src/cortex_core/subagents.py` states that the delegated run's deadline "sits
strictly between the two bounds either side of it, the pool's 600 s stall ceiling and its 3600 s
admission wait, so the three are ordered by the scope of what they bound". All three numbers are
now registry entries, and each is held to the places that state it. **The ordering is held by
nothing.** `scripts/couplings.py` has a `Relation.ORDERED` for exactly this shape, but it orders
the sites of ONE entry, and these are three entries in three modules. The boot-time check in
`brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py` covers one of the two
orderings the sentence claims (`run_timeout_s <= stall_timeout_s` is refused) and says nothing
about the run deadline against the admission wait, which the comment there notes is deliberate for
the zero setting.

So retuning the ceiling above the deadline is caught at boot, retuning the deadline above the wait
is caught nowhere, and the sentence asserting all three go on being green either way.

**Why it was left.** Each close in this run was about one value, and an ordering is about three.
Expressing it needs a decision the registry has never had to make: whether an entry may name a
site another entry also names, which is the same new edge the misattribution close refused for a
different reason.

**What would close it, and what to check first.** Re-derive before designing. The cheap shape is a
fourth entry with `Relation.ORDERED` over the three declaring sites, `DEFAULT_STALL_TIMEOUT_S`,
`DEFAULT_SUBAGENT_RUN_TIMEOUT_S` and `DEFAULT_ADMISSION_WAIT_S`, in that order, which the existing
relation already expresses and which needs no new vocabulary at all. Two things to check before
writing it: an ordering "compares integers" per `scripts/readings.py`, and all three of these are
decimals, so either the relation grows a decimal comparison or this shape is not available; and the
registry suite requires an entry to span more than one language, which an ordering over three
Python declarations does not, so that rule has to be argued about or the entry has to reach a far
side that is not Python.
