# Nothing checks a third CPU subagent server's thread count

**Status:** open, waiting for its trigger
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-10-07
**Trigger:** any compose file, either shipped subagent file included, starts a third subagent server
with `-ngl 0`, which `uv run python flagcheck.py --root ..` in `scripts/` counts in its success line
as a fourth server (three on 2026-09-19: the two CPU servers and the model host's hosted tier)

`flagcheck.py` refuses a CPU subagent server started without a thread count, in any compose file,
the day that file is written. What it does not read is the number after the flag. The right number
is the service's own `cpus` cap, and the two shipped servers are checked against it by one rendered
search string each, written per file in `scripts/subagentcouplings.py`. Each asks only that its flag
line and count appear in its file, so it covers the server it was written for and no other. A third
CPU server could therefore pass `--threads 32` inside a two-CPU quota and pass every check, whether
it arrives in a new compose file or beside a shipped server in one of the two shipped files, which
is the throttling the explicit count exists to prevent arriving another way.

**What would close it.** The fix
[R-638](638-a-cpu-subagent-server-in-a-third-compose-file-is-held-to-no-thread-count.md) declined: a
rule requiring a `-ngl 0` server's `--threads` to use the same substitution its own `cpus` key
reads, which needs `composestarts.py` to read a third service key and needs `Server` to have a field
the model host's hosted tier can never fill. It was declined on three grounds: the hosted tier is
no compose service and has no `cpus` key, comparing two ways of writing one value is the constant
scan's subject, and the line cap on the reader. The alternatives of
[ADR-0004](../../adr/ADR-0004-model-lineup.md) keep the first. The third does not hold:
`composestarts.py` is 212 lines of 300, so the key it would learn needs no split. Worth weighing
beside it: a wrong count inside a quota is a slow tier rather than a broken one, where a missing
flag decoded at about a twenty-fifth of the rate with the count set and took 13.7 times as long,
so the case now refused is the one that mattered.

## History

- 2026-09-15: opened by the close of
  [R-638](638-a-cpu-subagent-server-in-a-third-compose-file-is-held-to-no-thread-count.md), which
  requires the flag and leaves the value.
- 2026-09-19: not fired, and the subject was narrower than the defect. `flagcheck.py` still reads
  three subagent servers in three files, `composestarts.py` is still 250 lines, and the two search
  strings are unchanged. The entry said the value goes unchecked in a third compose file; it goes
  unchecked for any third CPU server. In a throwaway worktree, a service appended to
  `docker/docker-compose.subagents.yml` with all five required flags and a thread count of 32 under
  `cpus: 2.0` passed both checks: flagcheck counted four servers in three files and crosscheck
  reported 92 constants in agreement, the budget's substitution still appearing exactly three times
  in that file. The title, the trigger and the paragraph above now say so, and the fix stands, since
  a rule over each `-ngl 0` server's own argv and `cpus` key reaches a server in a shipped file as
  well as in a new one.
- 2026-10-01: not fired. `uv run python flagcheck.py --root ..` in `scripts/` reads three subagent
  servers in three files, the thread rule in `scripts/subagentflags.py` still requires the flag
  when `-ngl 0` is set and reads no value, and the two search strings in
  `scripts/subagentcouplings.py` are unchanged. Two claims in the paragraph above were wrong and
  are corrected. `composestarts.py` is 212 lines, as it was on 2026-09-19, so the line cap is no
  ground for declining the fix; and the alternatives of ADR-0004 keep one of the three grounds, not
  all three. The decode figure was a twentieth where the reading says a twenty-fifth.
- 2026-10-04: not fired. `uv run python flagcheck.py --root ..` in `scripts/` reads three subagent
  servers in three files and exits 0. The thread rule in `scripts/subagentflags.py` still requires
  the flag when `-ngl 0` is set and reads no value, `scripts/subagentcouplings.py` and the two
  subagent compose files are unchanged since 2026-10-01, and `composestarts.py` is still 212 lines.
