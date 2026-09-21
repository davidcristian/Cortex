# The replay sample and its window are written in four places

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Verified:** 2026-09-17
**Trigger:** the `replay` recipe's defaults line in the `justfile` stops reading `count="5" window="25"`, or any of the prose copies stops saying five and twenty five, since the copies come apart the moment one of them moves. A caller passing other values to `just replay` changes neither default and does not fire it.

Two numbers decide a replay pass, the sample of five and the window of twenty five, and each is
written four times: as a default parameter of the `replay` recipe in the `justfile`, in words in
the comment directly above that recipe, in the prose of
[docs/runbooks/mutation-replay.md](../../runbooks/mutation-replay.md), and in the ADR that decided
them. The default is the executable copy and the other three are the argument for it, so a retuned
default leaves three passages stating a rule the tool no longer follows.

No coupling was registered because `crosscheck.py` ties a value only where its registry names both
sides, and every restating place here is prose writing the numbers as words rather than digits.
Registering it is a registry entry plus its tests plus a search text that survives a sentence being
rewritten around it, which is more machinery than a number nobody has yet had a reason to change.

The alternative is that the prose stops naming the numbers and points at the recipe, which costs
the ADR its argument and is probably the wrong trade.

## History

- 2026-08-25: opened by the pass that gave the replay a cadence
  ([R-357](357-a-replay-pass-has-no-cadence.md), ADR-0002 decision 20).
- 2026-09-07: not fired, and the count above was low. Neither number has moved: the defaults line
  reads `count="5" window="25"` and has not been edited since the recipe was added, the runbook
  still says twenty five candidate commit bodies and five drawn, and the ADR still argues for those
  two numbers. The copies were recounted, and there are four of each rather than three. The fourth
  is in the `justfile` as well, in the comment above the recipe. That copy sits on the same screen
  as the default an editor would be retuning, so of the four it is the least likely to be left
  behind, and the two documents in `docs/` are the pair this entry is really about. The title says
  four now; the file name keeps the count it was opened under, being an identifier other documents
  already link to.
- 2026-09-10: still not fired, and all four copies of each number are where the last reading left
  them. `crosscheck.py` registers neither number.
- 2026-09-12: still not fired, the copies are unchanged at four of each, and registering one costs
  more than this file estimates. `crosscheck.py` reads a declaration by dispatching on the file's
  suffix and knows three, `.py`, `.rs` and `.ts`, so the `justfile`'s `count="5" window="25"`,
  which is the executable copy, cannot be a registered declaration at all until the scan learns a
  fourth syntax for a file that has no suffix. The word form this file names is the second obstacle
  rather than the only one, and closing it needs `Form` to grow a form rendering 25 as twenty
  five, a form being derived from the declared value rather than typed into the registry. Both are
  edits to the scan rather than registry entries. One sentence did move:
  `just replay` now reads the ledger's last date and compares the count against the same twenty
  five ([R-439](439-nothing-counts-the-record-between-passes.md)), using the recipe's `window`
  default in both roles rather than adding a fifth copy, so the runbook's cadence sentence states
  what a recipe does rather than what a reader should do.
- 2026-09-17: not fired, and still four places, though three of them write the numbers more than
  once. A search for the digits and the words over the `justfile`, the runbook, ADR-0002,
  AGENTS.md, `docs/modules/`, `scripts/` and the workflows finds them in: the defaults line
  (`justfile` line 323); the comment above the recipe (line 306); the runbook, in five sentences
  that state the rule (lines 16, 25, 61, 65 and 138) besides the ledger row at line 158, which
  records what one pass drew and is a dated reading rather than a copy; and the cadence decision in
  ADR-0002. Nothing in AGENTS.md, `docs/modules/`, `scripts/` or the workflows writes them. The
  runbook's five are the ones a retune would have to find by reading, since the recipe's own body
  uses `{{ window }}` and `{{ count }}` (lines 376 to 388) rather than copying them. The only
  change since the last reading, the commit that counts the current gap from the commit a pass drew
  from, moved neither number.
