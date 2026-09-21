# Nothing checks a third compose file's CPU subagent server for a thread count

**Status:** done 2026-09-15
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Both CPU subagent servers pass `--threads` from the substitution their `cpus` cap reads, and the
constant scan checks that pair by counting the substitution in each of the two files by name
(`scripts/subagentcouplings.py`). `scripts/flagcheck.py` derives every subagent server the tree
starts from the stack's own wiring and argv, so it would find a third one the day it is written, but
it did not require `--threads` of it: its rule runs over both placements of the tier, and the model
host's hosted subagent tier is a GPU tier with no per-tier quota, while the right value of the count
is the service's own `cpus` substitution, a relation between two keys of one service that the
compose reader under `flagcheck.py` does not read. So a third CPU subagent server written without
the flag would run one thread per hardware thread inside its quota and pass every check.

**What closed it.** `Requirement` gained a `when` field, the flag and value a server must already be
started with for the requirement to apply, and the thread entry names `-ngl 0`, so it covers both
CPU servers and passes over the hosted GPU tier. It checks the flag and not the number after it.

The larger version, requiring a `-ngl 0` server's `--threads` to use the same substitution its own
`cpus` key reads, was declined on three grounds, summarised in the alternatives of
[ADR-0004](../../adr/ADR-0004-model-lineup.md): a `cpus` key is a field half the set cannot answer,
since the hosted tier is no compose service; comparing two ways of writing one value is the constant
scan's subject and it already covers this pair per file; and `composestarts.py`, the reader that
would learn the key, is at 250 lines of the 300 cap.

## History

- 2026-09-11: opened by the close of
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md), whose origin
  record says why the count did not join `flagcheck.py`'s requirements.
- 2026-09-11: the review of that change found a second side of the same gap, on the two files this
  entry treats as covered. The constant scan counts the substitution, not the flag in front of it,
  so renaming `--threads` to `--threads-batch` on either server, with the substitution kept, left
  `crosscheck.py`, `defaultcheck.py` and `flagcheck.py` all exiting 0. The file was restored from a
  saved copy after each run, and no comment or document claimed the flag name was checked.
- 2026-09-12: the reason the previous bullet gave for choosing the conditional requirement is wrong,
  and the flag name is now checked on both shipped servers. A rendered search string is matched
  against the whole file with `re.finditer` (`scripts/searchtexts.py`), so it may include the
  newline and the indentation between two argv items. The CPU budget's constant now has one such
  string per file, the `- "--threads"` line and the substitution line under it, and four mutations
  fail it that passed before: the flag renamed on either server, the flag line dropped with its
  value kept, and the count moved ahead of its own flag. Recorded in the thread-flag change of
  2026-09-12 ([ADR-0004](../../adr/ADR-0004-model-lineup.md)). This entry's own subject is
  untouched, since a search string is written per file. `uv run python flagcheck.py --root ..` in
  `scripts/` on this date reads three servers in three files, the two CPU servers and the hosted GPU
  tier.
- 2026-09-15: the trigger is still unfired, and a second, smaller fix is worth writing down: a
  requirement predicated on the argv alone, requiring every server started with `-ngl 0` to have a
  `--threads` at all. It needs no new compose key and refuses the configuration the explicit count
  exists to prevent, while leaving the count's value to the per-file search string. Either version
  adds a field to `Requirement` and a predicate to `check_one`, and `flagcheck.py` is 265 lines
  against the 300-line cap, so either also moves the requirements into a module beside it. Recorded
  in the delegated-memory reading of 2026-09-15 ([model lineup](../../readings/model-lineup.md)).
- 2026-09-15, later: done, as the cheaper of the two. The rule and the reading of one flag against
  one argv moved into `scripts/subagentflags.py`, taking `flagcheck.py` from 265 lines to 175. The
  trigger's own case was then run by hand: a third compose file starting a `-ngl 0` server with
  every other flag and no `--threads` made `uv run python flagcheck.py --root ..` exit 1 naming that
  file and that entry, where the same file passed before. Six mutations of the rule take down 4 to
  25 tests of the `scripts/` suite. The count's value in a file nobody has written yet is left open
  as [R-676](676-a-third-compose-files-thread-count-is-held-to-no-value.md).
