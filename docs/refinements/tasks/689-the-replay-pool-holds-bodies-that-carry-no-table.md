# The replay pool holds bodies that carry no table

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Verified:** 2026-09-19

Opened 2026-09-19 by the third mutation replay pass, recorded in the ledger of
[docs/runbooks/mutation-replay.md](../../runbooks/mutation-replay.md) and in the ADR-0002 addendum
of that date.

The `replay` recipe in the `justfile` finds its candidates by four patterns over commit messages:
`redden`, `mutant`, `mutation` and `prove[a-z]* able to fail`. Since the replay practice has a
name, a body that talks about it matches as well as a body that carries a table. Of the 25 bodies in
the window at `7088d204`, fifteen carry a table their own commit measured and ten do not: four
backlog sweeps, a fifth sweep that retook the vocabulary census, the commit that gave the recipe its
standing count, a live matrix row that says it owes no table, a replay of recorded marks, a commit
that points at the table the commit before it landed, and the plain-language rewrite of the whole
corpus, which matched on `redden`, the word it retired. The 2026-09-19 pass drew three of the ten
among its five: two carry no table at all, and the third points at another commit's table, which
the pass replayed for it.

That has two costs. A pass of five draws replays about three tables, and the cadence of 25
candidate bodies was about fifteen tables when this was measured. The patterns cannot separate the
two kinds on the message alone: every tableless body in that window but the rewrite matches only
on `mutation` (`mutation replay`, `mutation table`, `mutation ledger`), and so do three bodies that
carry tables (`Four mutations fail it`, `Six mutations left`, `mutation table over the scripts
suite`).

**What would close it.** The runbook tells a pass to record a drawn body that carries no table its
own commit measured as tableless and to take the next body in the same seed's order at the same
commit, which `just replay <seed> "" <n>` prints with the first five unchanged, so the replacement
is as blind as the draw. At `7088d204` seed 26747890's sixth body is also tableless and its seventh
and eighth carry tables, so that pass would have replayed those two. The change is a runbook
paragraph and an ADR-0002 addendum. Whether the cadence should then count tables rather than bodies
is a question for the same change to answer from its own reading of the window, since counting
tables needs the judgement a pass applies and the recipe does not.

## Trail

- 2026-09-19: opened by the third replay pass, which replayed the fifteen mutation rows of the three
  tables it drew, all reproducing, and retook the readings of the two bodies that carry none.
