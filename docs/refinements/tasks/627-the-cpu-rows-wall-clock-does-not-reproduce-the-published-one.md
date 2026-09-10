# The CPU row's wall clock does not reproduce the published one

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-10

Opened 2026-09-10 by the close of
[R-617](617-the-picks-published-cpu-row-was-drawn-before-the-memory-cap.md), which drew the subagent
pick's CPU row twice and got 717.73 s and 711.02 s where the 2026-09-05 sitting got 1837 s, on
counts that replicated cell for cell in both.

**What is known.** The three sittings ran the same ten attacks in two arms at the same 1600-token
budget, on the same CPU image (`ghcr.io/ggml-org/llama.cpp:server` at `sha256:db057ec90de0`), with
the same tier argv, and the only declared difference is the two memory caps the later pair adds. A
cap cannot account for the direction: it withholds memory rather than granting it. The 2026-09-05
table holds a third figure that rules the cgroup shape out on its own, an 819 s row drawn with no
quota at all, so the fastest sittings are the most constrained ones. The two sittings drawn on
2026-09-10 are 6.71 s apart, 0.9% of either, and the second was drawn at a load average of 1.40
against the first's 0.33 and came back the faster of the two, so at these loads the figure is not
tracking the other work on the box either.

**The candidate nobody has measured.** Neither the harness nor
`docker/docker-compose.subagents.yml` passes `--threads`, so `llama-server` takes its own default,
which is one thread per hardware thread the container sees. That is 24 here, inside a quota of 4.0
CPUs, and how 24 runnable threads share 4 CPUs depends on the scheduler and on what the machine
looked like that day. The 2026-09-05 sitting's load is not recorded, and its host state is now
unrecoverable. This is a hypothesis about the gap, not a measurement of it.

**Why it matters beyond the table.** The deployment runs the same unpinned thread count, so
whatever the answer is, it is the shipped subagent server's answer too, not an artifact of the
probe. A thread count pinned to the quota would also make every future row on this tier comparable
to every past one, which is what the published table wants from a wall-clock column.

**What would close it.** One pair of sittings of `pytest -k "E4B and cpu and shipped-argv"`, one
with `--threads` pinned to the quota and one without, drawn back to back with each box state
recorded, which says whether the unpinned count is the variance or merely beside it. The spread the
entry needed to make that comparison readable already exists, at 0.9% over two sittings, so a
difference larger than that is a difference.

## Trail

- 2026-09-10: opened by the close of
  [R-617](617-the-picks-published-cpu-row-was-drawn-before-the-memory-cap.md). The redraw the entry
  asked for replicated every count and moved the wall clock by a factor of 2.56, which is the one
  reading it could not attribute, so the attribution is carried here. A second sitting drawn the
  same morning gave the shape its spread and narrowed this entry from two questions to one.
