# The CPU row's wall clock is not reproducible across sittings

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-10

Opened 2026-09-10 by the close of
[R-617](617-the-picks-published-cpu-row-was-drawn-before-the-memory-cap.md), which drew the subagent
pick's CPU row a second time and got 717.73 s where the 2026-09-05 sitting got 1837 s, on counts
that replicated cell for cell.

**What is known.** The two sittings ran the same ten attacks in two arms at the same 1600-token
budget, on the same CPU image (`ghcr.io/ggml-org/llama.cpp:server` at `sha256:db057ec90de0`), with
the same tier argv, and the only declared difference is the two memory caps the later sitting adds.
A cap cannot account for the direction: it withholds memory rather than granting it. The 2026-09-05
table holds a third figure that rules the cgroup shape out on its own, an 819 s row drawn with no
quota at all, so the fastest of the three sittings is the most constrained one.

**The candidate nobody has measured.** Neither the harness nor
`docker/docker-compose.subagents.yml` passes `--threads`, so `llama-server` takes its own default,
which is one thread per hardware thread the container sees. That is 24 here, inside a quota of 4.0
CPUs, and how 24 runnable threads share 4 CPUs depends on what else is on the box. Both sittings
above were drawn on a machine whose other load was not recorded, and today's was drawn at a load
average of 0.33 with no other container running. This is a hypothesis about the variance, not a
measurement of it.

**Why it matters beyond the table.** The deployment runs the same unpinned thread count, so
whatever the answer is, it is the shipped subagent server's answer too, not an artifact of the
probe.

**What would close it.** Two or three sittings of `pytest -k "E4B and cpu and shipped-argv"` on a
box whose load is recorded with each, which turns a difference between two numbers into a spread; and
one pair drawn with `--threads` pinned to the quota against one drawn without, which says whether
the unpinned count is the variance or merely beside it.

## Trail

- 2026-09-10: opened by the close of
  [R-617](617-the-picks-published-cpu-row-was-drawn-before-the-memory-cap.md). The redraw the entry
  asked for replicated every count and moved the wall clock by a factor of 2.56, which is the one
  reading it could not attribute, so the attribution is carried here.
