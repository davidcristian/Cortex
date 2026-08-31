# The gate on a mutation table's wording is refused by the corpus, not by the idea

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** the last fifty commit bodies that carry a mutation table all name a path this
repository tracks and name the suite their counts are over, at which point the refusal rate that
refused the gate is zero
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Opened 2026-08-21 by the close of [R-349](349-a-mutation-table-nobody-replayed.md), which weighed
making replayability a requirement `commitlint.py` enforces and declined it on a census rather than
on principle. The decline is worth keeping revisitable, because both halves of it are measurements
of a corpus and a corpus moves.

**The two numbers that refused it.** Over 561 commits, 100 bodies carry the vocabulary a table is
written in, and 88 of the 100 name no path this repository tracks. A rule the established register
violates 88 times out of 100 declares the practice a violation rather than catching a defect. And
the detector needs three patterns to see those 100 at all, only 54 of them using `reddens`, while
one of the 100 is a change whose body says there is no assertion to prove able to fail, so the
gate's first report would be a false failure against a message that was accurate.

**Why the trigger is the accurate form of the decline.** AGENTS.md now requires a mutation table to
name the suite its counts are over, as a rule no machine checks. If that requirement takes hold,
recent bodies converge on naming both a suite and a file, and the refusal rate that refused the gate
falls out of the corpus on its own. At that point the rule stops demanding a rewrite of accurate
messages and becomes a check that a habit did not lapse, which is a different check under the same
regex. Measuring the refusal rate again is the census script from the close, about thirty lines, so
firing this trigger costs a reading rather than a build.

**What it would still not buy, and what to write down instead of pretending otherwise.** Naming a
path is satisfiable by naming any path, so the gate would hold the presence of a coordinate and
never its relevance. That is a weak check and it should be landed as one, with its message saying
what it checks, or not landed at all. The stronger half, that the table names the suite its counts
are over, has no machine form: a suite is prose, spelled `just check-brain` one day and "the
orchestrator's own cases" the next, and prescribing the spelling is prescribing the register.
