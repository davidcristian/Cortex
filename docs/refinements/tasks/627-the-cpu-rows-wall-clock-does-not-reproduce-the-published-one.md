# The CPU row's wall clock does not reproduce the published one

**Status:** landed 2026-09-11
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

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

**Pre-registered 2026-09-11, before either sitting ran.** Four things are fixed here so the
reading is not chosen after the numbers are in.

- *What the pair is.* Two sittings of the same node id, drawn one after the other on the same
  box, an unpinned one under the shape the harness starts today and a pinned one whose server
  carries `--threads 4` on top of that shape, 4 being the quota `DEFAULT_CPU_BUDGET` prints. The
  flag is appended from outside the tree by a pytest plugin that wraps `server_argv`, so the
  harness is unchanged; the container's own command line is read back with `docker inspect` and
  the thread count the server chose is read off its `system_info` log line in both sittings. The
  artifact is read through from the host once before the first sitting, so that neither sitting
  pays a cold read from the drvfs bind that the other does not. The second 2026-09-10 sitting
  started with the artifact resident the same way, from the first, and drew inside the spread.
- *What is a difference.* The two 2026-09-10 sittings are 0.9% apart, so a wall clock more than
  0.9% from the unpinned sitting's is a difference and one within it is a replicate.
- *What each outcome means.* The pinned sitting faster than the unpinned one by more than 0.9%
  says the thread count is a lever on this row's wall clock, and the reading then recommends
  pinning it to the quota in `docker/docker-compose.subagents.yml`, which is the owner's default
  to change and is not changed here. The two within 0.9% of each other say the thread count is not
  what the wall clock tracks at this box's load, and the published 1837 s stays unattributed with
  no candidate left in this entry. The pinned sitting slower by more than 0.9% says the default's
  oversubscription is faster under the quota than a pinned count is, and nothing is recommended.
  No outcome reproduces the 2026-09-05 box, so none can say what 1837 s was; the pair says
  whether the count is a lever, which is the whole of what the entry asks.
- *What the counts are compared against.* Both sittings are expected to replicate 0 framed and
  1 control, the control's one cell on `refusal-suppression`. A thread count changes the order the
  engine reduces a matrix product in, which at temperature 0 can move a token, so a moved cell in
  the pinned sitting is reported as that sitting's and is not read as the resistance moving.

**Drawn 2026-09-11.** The pair is published in the
[pinned-thread addendum](../../adr/ADR-0004-model-lineup.md#addendum-2026-09-11-the-picks-cpu-row-is-drawn-with-its-thread-count-pinned-to-the-quota-and-the-count-is-the-wall-clock).
The unpinned sitting came back at 1560.15 s and the pinned one at 114.08 s, a factor of 13.7, on
counts that replicate cell for cell in both, and a second pinned sitting drawn for the spread came
back at 114.86 s. The server's own timing lines put unpinned decoding at 0.43 to 0.54 tokens a
second and pinned at 11.9 to 12.4, and the container's `cpu.stat` put the unpinned cgroup throttled
in 14,308 of 14,520 periods. The first outcome pre-registered above is the one that happened: the
thread count is a lever on this row's wall clock, and the four unpinned sittings of this row, 711 s
to 1837 s, are one shape whose figure depends on how the scheduler distributes the quota over 24
threads that never sleep. The published 1837 s is attributed to that, which is what this entry
asked.

## Trail

- 2026-09-10: opened by the close of
  [R-617](617-the-picks-published-cpu-row-was-drawn-before-the-memory-cap.md). The redraw the entry
  asked for replicated every count and moved the wall clock by a factor of 2.56, which is the one
  reading it could not attribute, so the attribution is carried here. A second sitting drawn the
  same morning gave the shape its spread and narrowed this entry from two questions to one.
- 2026-09-11: the pair was drawn as pre-registered, plus one more pinned sitting for the spread. The
  thread count is the wall clock, by a factor of 13.7, and the pinned shape reproduces to 0.7%. The
  recommendation to pin `--threads` to the quota in `docker/docker-compose.subagents.yml` is the
  owner's default to set and is carried, with what follows from it, by
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md). The same
  sittings read the memory cap binding under the harness's budget, which is
  [R-629](629-the-picks-cpu-server-reaches-its-memory-cap-under-the-harnesss-budget.md).
