# A CPU subagent server in a third compose file is held to no thread count

**Status:** landed 2026-09-15
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Opened 2026-09-11 by the close of
[R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md).

**What is known.** Both CPU subagent servers now pass `--threads` from the substitution their `cpus`
cap reads, and the constant scan holds that pair by counting the substitution in each of the two
files by name (`scripts/subagentcouplings.py`). The flag gate derives every subagent server the
tree starts from the stack's own wiring and argv, so it would find a third one the day it is
written, but it does not require `--threads` of it. That was decided at the close: the flag gate's
rule runs over both placements of the tier, and the model host's hosted subagent tier is a GPU tier
with no per-tier quota a count could be pinned to, while the right value of the count is the
service's own `cpus` substitution, a relation between two keys of one service that the compose
reader under the flag gate does not read. So a third CPU subagent server written without the pin
would run one thread per hardware thread inside its quota and pass every gate.

**What would close it.** Either a conditional requirement in `flagcheck.py`, holding every compose
server started with `-ngl 0` to a `--threads` that spells the same substitution as its `cpus` key,
which means `composestarts.py` learning to read that key; or the new file's two spellings added to
the CPU budget's constant in the registry, which is the shape the roster file's server took. The
second is per file by construction, so it answers a file once it is written and never in advance,
which is why the first is still what closes this entry.

## Trail

- 2026-09-11: opened by the close of
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md), whose origin
  addendum records why the count did not join the flag gate's requirements.
- 2026-09-11: the review of the landing found a second face of the same gap, on the two files
  this entry treats as held. The constant scan counts the substitution, not the flag in front of
  it, so renaming `--threads` to `--threads-batch` on either server, with the substitution kept,
  left `crosscheck.py`, `defaultcheck.py` and `flagcheck.py` all exiting 0. The file was restored
  from a saved copy after each run. No comment or document claims the flag name is held. The
  finding decides between the two remedies above: only the conditional requirement in
  `flagcheck.py` holds the flag and its value together, because each sits on its own argv line
  and a registry needle reads one line. That remedy is the one to build when the trigger fires,
  and the status stays as it is because a rename of that flag is an edit nobody has made.
- 2026-09-12: **the reason the entry above gave for choosing that remedy is wrong, and the flag
  name is now held on both shipped servers.** A rendered needle is matched against the whole file
  with `re.finditer` (`scripts/needles.py`), so it may carry the newline and the indentation
  between two argv items. The CPU budget's constant now carries one such needle per file, the
  `- "--threads"` line and the substitution line under it, and four mutations fail it that passed
  before: the flag renamed on either server, the flag line dropped with its value kept, and the
  count moved ahead of its own flag. Recorded in the
  [ADR-0004 thread-flag addendum](../../adr/ADR-0004-model-lineup.md).
  This entry's own subject is untouched: a needle is written per file, so a CPU subagent server in
  a file nobody has written yet is still held to no count, and closing that is still the flag
  gate's. The trigger is unfired, read out of `uv run python flagcheck.py --root ..` in `scripts/`
  on this date: three servers in three files, which are the two CPU servers and the model host's
  hosted GPU tier.
- 2026-09-15: **the trigger is still unfired, and a second remedy is worth writing down.**
  `uv run python flagcheck.py --root ..` in `scripts/` reads three subagent servers in three files,
  the two CPU servers and the model host's hosted GPU tier. Beside the conditional requirement this
  entry records, which holds a `-ngl 0` server's `--threads` to the same substitution its own `cpus`
  key reads and needs `composestarts.py` to learn a third service key, there is a smaller one: a
  requirement predicated on the argv alone, holding every server started with `-ngl 0` to carrying a
  `--threads` at all. It needs no new compose key and refuses the shape the pin exists to prevent,
  the engine's own default of one thread per hardware thread, while leaving the count's value to the
  per-file needle. Either adds a field to `Requirement` and a predicate to `check_one`, and
  `flagcheck.py` is 265 lines against the 300-line cap, so either also moves the requirements into a
  module beside it. Recorded in the
  [ADR-0004 delegated-memory addendum](../../adr/ADR-0004-model-lineup.md).
- 2026-09-15, later: **landed**, as the cheaper of the two remedies. `Requirement` gained a `when`
  field, the flag and value a server must already be started with for the requirement to reach it,
  and the thread entry names `-ngl 0`, so it holds both CPU servers and passes over the model host's
  hosted GPU tier. What the entry asks is the flag and not the number after it. The larger remedy
  was declined on three grounds, written up in the [ADR-0004 thread-count
  addendum](../../adr/ADR-0004-model-lineup.md):
  a `cpus` key is a field half the set cannot answer, since the hosted tier is no compose service;
  comparing two spellings of one value is the constant scan's subject and it already holds this pair
  per file; and `composestarts.py`, the reader that would learn the key, is at 250 lines of the 300
  cap. The rule and the reading of one flag against one argv moved into `scripts/subagentflags.py`,
  taking `flagcheck.py` from 265 lines to 175. The trigger's own shape was then run by hand: a third
  compose file starting a `-ngl 0` server with every other flag and no `--threads` made
  `uv run python flagcheck.py --root ..` exit 1 naming that file and that entry, where the same file
  passed before. Six mutations of the rule take down 4 to 25 tests of the `scripts/` suite. The
  count's value in a file nobody has written yet is left open as
  [R-676](676-a-third-compose-files-thread-count-is-held-to-no-value.md).
