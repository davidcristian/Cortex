# A check on a mutation table's wording was refused by the corpus, not by the idea

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Trigger:** at least fifty commit messages match the `replay` recipe's vocabulary (`git log -i -E
--grep=redden --grep=mutant --grep=mutation --grep='prove[a-z]* able to fail'`, 17 on 2026-09-19),
and the most recent fifty of them all name a path this repository tracks and the suite their counts
are over, at which point the refusal rate that refused the check is zero. The path half is a script
over `git ls-files`; the suite half is a reader's judgement, having no machine form
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Verified:** 2026-09-19

This was opened on 2026-08-21 by the close of [R-349](349-a-mutation-table-nobody-replayed.md),
which weighed making replayability a requirement `commitlint.py` enforces and declined it on a
census rather than on principle. Both halves of the
decline are measurements of a corpus, and a corpus moves.

The two numbers that refused it: over 561 commits, 100 bodies use the vocabulary a table is written
in, and 88 of the 100 name no path this repository tracks. A rule the established style violates 88
times out of 100 declares the practice a violation rather than catching a defect. The detector also
needs three patterns to find those 100 at all, only 54 of them using `reddens`, and one of the 100
is a change whose body says there is no assertion to prove able to fail, so the check's first
report would be a false failure against an accurate message.

AGENTS.md now requires a mutation table to name the suite its counts are over, as a rule no machine
checks. If that takes hold, recent bodies converge on naming both a suite and a file, and the
refusal rate falls out of the corpus on its own. Measuring it again is the census script, about
thirty lines, so firing this trigger costs a reading rather than a build.

What it would still not buy: naming a path is satisfiable by naming any path, so the check would
find the presence of a coordinate and never its relevance. That is a weak check and should be added
as one, with its message saying what it checks, or not added at all. The stronger half, that the
table names the suite its counts are over, has no machine form, a suite being prose.

## History

- 2026-09-11: Not fired, and the population the trigger counts has moved. Re-taken over all 797
  commit bodies, 12 match the recipe's four patterns and 11 of those name no path this repository
  tracks, so the whole history is far under the fifty the trigger asks for. A body says in one
  sentence that the change was proved by mutation and the table itself is written elsewhere, so a
  rule in `commitlint.py` would read the place the tables have left.
- 2026-09-17: Not fired, and the population is still short of fifty. Re-taken over all 912
  commits: 16 messages match, and a scratch detector matching a tracked path or file name finds 15
  of the 16 naming none and none naming both a path and a suite word. The matches over-count the
  tables, since the practice is named in bodies that have none, so a rule keyed off the vocabulary
  would misfire on accurate messages. The trigger now names the command that counts the
  population, since the close's census was never committed, and says which of its two halves a
  script can decide.
- 2026-09-19: Not fired. The recipe's four patterns match 17 messages of 954, and 16 of the 17
  name no path this repository tracks. A body of two or three sentences names the practice rather
  than describing it, so the vocabulary the detector would read is not growing toward fifty.
