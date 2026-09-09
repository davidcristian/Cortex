# The pick's published CPU row was drawn before the memory cap

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-09

Opened 2026-09-09 by the close of
[R-559](559-the-cpu-row-carries-the-cpu-quota-and-not-the-memory-cap.md), which gave the injection
harness's CPU placement the subagents override's `mem_limit` and `memswap_limit` alongside the
`cpus:` quota it already had.

The subagent pick's CPU row in the
[placement-row addendum](../../adr/ADR-0004-model-lineup.md#addendum-2026-09-05-every-row-starts-with-its-tiers-own-command-line-and-the-subagent-pick-has-a-cpu-row)
was drawn on 2026-09-05 under the quota alone: 0 of 10 framed, 1 of 10 on the unframed control,
1837 s of wall clock at about 0.4 tokens a second. Every CPU row drawn after 2026-09-09 carries the
two memory caps as well, so the table holds one row taken under a shape the harness no longer
starts.

**Why the pick is the row where this could matter.** Its server is the one measured at 90.4% of the
8 GiB limit, 0.77 GiB of headroom, with 4.79 GiB of that charge being the artifact mapped from the
read-only bind. What the cap bounds on this pick is how much of the artifact stays cached under
pressure, and a page lost is a re-read from a drvfs bind, which is the slowest read on this host.
The four smaller candidates have gigabytes of headroom under the same cap, so the risk is specific
to this row. Nothing says the resistance counts move; the wall clock is the reading with something
to lose.

**What would close it.** One sitting of `pytest -k "E4B and cpu and shipped-argv"` under the row's
current shape, published beside the 2026-09-05 row so the two shapes are comparable, and a reading
of whether the framed count or the wall clock moved.

## Trail

- 2026-09-09: opened by the close of
  [R-559](559-the-cpu-row-carries-the-cpu-quota-and-not-the-memory-cap.md), which added both memory
  caps to the CPU placement and left the pick's published row under the older shape.
