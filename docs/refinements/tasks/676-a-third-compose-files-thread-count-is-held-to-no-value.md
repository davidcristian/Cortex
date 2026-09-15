# A third compose file's thread count is held to no value

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-15
**Trigger:** a compose file other than `docker/docker-compose.subagents.yml` and
`docker/docker-compose.subagents-roster.yml` starts a subagent server with `-ngl 0`, which
`uv run python flagcheck.py --root ..` in `scripts/` counts in its success line as a fourth server
or a fourth file

Opened 2026-09-15 by the close of
[R-638](638-a-cpu-subagent-server-in-a-third-compose-file-is-held-to-no-thread-count.md), which
held every `-ngl 0` subagent server to carrying a `--threads` at all.

**What is known.** The flag gate now refuses a CPU subagent server started without a thread count,
in any compose file, the day that file is written. What it does not read is the number after the
flag. The right number is the service's own `cpus` cap, and the two shipped files are held to it by
a rendered needle each, written per file in `scripts/subagentcouplings.py`. A third file's server
could therefore carry `--threads 32` inside a two-CPU quota and pass every gate, which is the
throttling the pin exists to prevent arriving under a different spelling.

**What would close it.** The remedy R-638 declined: a requirement holding a `-ngl 0` server's
`--threads` to the same substitution its own `cpus` key reads, which needs `composestarts.py` to
read a third service key and needs `Server` to carry a field the model host's hosted tier can never
fill. The three grounds it was declined on are in the [ADR-0004 thread-count
addendum](../../adr/ADR-0004-model-lineup.md),
and the one that would move first is the line cap: `composestarts.py` is at 250 lines of 300, so the
key it learns arrives with a split. The alternative worth weighing beside it is that a wrong count
inside a quota is a slow tier rather than a broken one, where a missing flag was measured at a
twentieth of the pinned decode rate, so the shape now refused is the one that mattered.

## Trail

- 2026-09-15: opened by the close of
  [R-638](638-a-cpu-subagent-server-in-a-third-compose-file-is-held-to-no-thread-count.md), whose
  landing holds the flag and leaves the value.
