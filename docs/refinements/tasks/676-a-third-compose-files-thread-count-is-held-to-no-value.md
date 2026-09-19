# A third CPU subagent server's thread count is held to no value

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-19
**Trigger:** any compose file, either shipped subagent file included, starts a third subagent
server with `-ngl 0`, which `uv run python flagcheck.py --root ..` in `scripts/` counts in its
success line as a fourth server (three on 2026-09-19: the two CPU servers and the model host's
hosted tier)

Opened 2026-09-15 by the close of
[R-638](638-a-cpu-subagent-server-in-a-third-compose-file-is-held-to-no-thread-count.md), which
held every `-ngl 0` subagent server to carrying a `--threads` at all.

**What is known.** The flag gate now refuses a CPU subagent server started without a thread count,
in any compose file, the day that file is written. What it does not read is the number after the
flag. The right number is the service's own `cpus` cap, and the two shipped servers are held to it
by a rendered needle each, written per file in `scripts/subagentcouplings.py`. Each needle asks
only that its flag line and count appear in its file, so it holds the server it was written for
and no other. A third CPU server could therefore carry `--threads 32` inside a two-CPU quota and
pass every gate, whether it arrives in a new compose file or beside a shipped server in one of the
two shipped files, which is the throttling the pin exists to prevent arriving under a different
spelling.

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
- 2026-09-19: **unfired, and the subject was narrower than the defect.** `flagcheck.py` still reads
  three subagent servers in three files, `composestarts.py` is still 250 lines, and the two needles
  are unchanged. The entry said the value goes unheld in a third compose file; it goes unheld for
  any third CPU server. In a throwaway worktree, a service appended to
  `docker/docker-compose.subagents.yml` carrying all five flags the gate requires, its thread count
  32 under `cpus: 2.0`, passed both gates: flagcheck counted four servers in three files and crosscheck
  reported 92 constants in agreement, the budget's substitution still spelled exactly three times
  in that file. The title, the trigger and the paragraph above now say so, and the remedy stands,
  since a requirement over each `-ngl 0` server's own argv and `cpus` key reaches a server in a
  shipped file as well as in a new one.
