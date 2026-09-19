# The CPU row's wall clock does not reproduce the published one

**Status:** done 2026-09-11
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

The subagent pick's CPU row was drawn twice on 2026-09-10 at 717.73 s and 711.02 s where the
2026-09-05 run got 1837 s, on counts that repeated cell for cell in all three.

**What is known.** The three runs ran the same ten attacks in two conditions at the same 1600-token
budget, on the same CPU image (`ghcr.io/ggml-org/llama.cpp:server` at `sha256:db057ec90de0`), with
the same tier argv, and the only declared difference is the two memory caps the later pair adds. A
cap cannot explain the direction, since it withholds memory rather than granting it. The 2026-09-05
table has a third figure that rules the cgroup configuration out on its own, an 819 s row drawn with
no quota at all, so the fastest runs are the most constrained ones. The two runs on 2026-09-10 are
6.71 s apart, 0.9% of either, and the second was drawn at a load average of 1.40 against the first's
0.33 and came back faster, so at these loads the figure does not track the other work on the box
either.

**The candidate nobody has measured.** Neither the harness nor
`docker/docker-compose.subagents.yml` passes `--threads`, so `llama-server` takes its own default of
one thread per hardware thread the container sees. That is 24 here, inside a quota of 4.0 CPUs, and
how 24 runnable threads share 4 CPUs depends on the scheduler and on what the machine looked like
that day. The 2026-09-05 run's load is not recorded and its host state is unrecoverable, so this is
a hypothesis about the gap rather than a measurement of it. The deployment runs the same thread
count, so whatever the answer is, it is the shipped subagent server's answer too.

**Written down 2026-09-11, before either run.** Two runs of the same node id, one after the other
on the same box: one under the configuration the harness starts today, and one whose server also
gets `--threads 4`, 4 being the quota `DEFAULT_CPU_BUDGET` gives. The flag is appended from outside
the tree by a pytest plugin that wraps `server_argv`, so the harness is unchanged; the container's
own command line is read back with `docker inspect` and the thread count the server chose is read
off its `system_info` log line in both runs. The artifact is read through from the host once before
the first run, so neither pays a cold read from the drvfs bind that the other does not. The two
2026-09-10 runs are 0.9% apart, so a wall clock more than 0.9% from the first run's is a difference.
A faster fixed-count run means the thread count changes this row's wall clock, and the reading then
recommends setting it from the quota in `docker/docker-compose.subagents.yml`, which is the owner's
default to change. Two runs within 0.9% mean the thread count is not what the wall clock tracks at
this box's load. A slower fixed-count run means the default's oversubscription is faster under the
quota. No outcome reproduces the 2026-09-05 box, so none can say what 1837 s was. Both runs are
expected to repeat 0 framed and 1 control, the control's one cell on `refusal-suppression`; a thread
count changes the order the engine reduces a matrix product in, which at temperature 0 can move a
token, so a moved cell is reported as that run's rather than read as the resistance moving.

**Drawn 2026-09-11.** The pair is published in the fixed-thread-count run of 2026-09-11
([injection text rows](../../readings/injection-text-rows.md)). The default-count run came back at
1560.15 s and the fixed-count one at 114.08 s, a factor of 13.7, on counts that repeat cell for cell
in both, and a second fixed-count run drawn for the spread came back at 114.86 s. The server's own
timing lines put default-count decoding at 0.43 to 0.54 tokens a second and fixed-count at 11.9 to
12.4, and the container's `cpu.stat` put the default-count cgroup throttled in 14,308 of 14,520
periods. So the thread count is what changes this row's wall clock, and the four default-count runs
of this row, 711 s to 1837 s, are one configuration whose figure depends on how the scheduler
distributes the quota over 24 threads that never sleep. The published 1837 s is explained by that.

## History

- 2026-09-10: opened by the close of
  [R-617](617-the-picks-published-cpu-row-was-drawn-before-the-memory-cap.md). The redraw that entry
  asked for repeated every count and moved the wall clock by a factor of 2.56, which it could not
  explain. A second run drawn the same morning gave the spread and narrowed this entry from two
  questions to one.
- 2026-09-11: the pair was drawn as written down, plus one more fixed-count run for the spread. The
  thread count is the wall clock, by a factor of 13.7, and the fixed-count configuration repeats to
  0.7%. The recommendation to set `--threads` from the quota in
  `docker/docker-compose.subagents.yml` is the owner's default to set and is handled, with what
  follows from it, by
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md). The same runs
  read the memory cap binding under the harness's budget, which is
  [R-629](629-the-picks-cpu-server-reaches-its-memory-cap-under-the-harnesss-budget.md).
