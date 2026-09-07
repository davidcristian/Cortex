# The replay sample and its window are spelled in four places

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** a change to either number, since the copies drift the moment one of them moves.

Opened 2026-08-25 by the pass that gave the replay a cadence
([R-357](357-a-replay-pass-has-no-cadence.md), [ADR-0002 replay-cadence
addendum](../../adr/ADR-0002-toolchain-gates.md)). Two numbers decide that pass, the sample of five
and the window of twenty five, and each is written four times: as a default parameter of the
`replay` recipe in the `justfile`, in words in the comment directly above that recipe, in the prose
of [docs/runbooks/mutation-replay.md](../../runbooks/mutation-replay.md), and in the addendum that
decided them. The default is the executable copy and the other three are the argument for it, so a
retuned default leaves three passages stating a rule the tool no longer follows.

**Why no coupling was registered on the spot.** `crosscheck.py` ties a value only where its
registry names both sides, and every far side here is prose spelling the numbers as words rather
than digits, which is the kind of mention that registry reads through a needle rather than a
literal. Registering it is a registry entry plus its tests plus a needle that survives a sentence
being rewritten around it, which is more machinery than a number nobody has yet had a reason to
change. The precedent for leaving it alone is the four shuffle seeds, deliberately unregistered,
though that argument is the opposite of this one: those are four independent values that must not
be tied, while these are one value each, spelled four times.

**What would close it.** Either a registered coupling holding the recipe's defaults against the
sentences that state them, or a decision that the prose stops naming the numbers and points at the
recipe for them, which costs the addendum its argument and is probably the wrong trade.

## Trail

- 2026-09-07: not fired, and the count above was low. Neither number has moved: the defaults line
  reads `count="5" window="25"` and has not been edited since the recipe was added, the runbook
  still says twenty five candidate bodies and five drawn, and the addendum still argues for those
  two numbers. The copies were recounted rather than the claim rechecked, and there are four of
  each rather than three. The fourth is in the `justfile` as well, in the comment above the recipe,
  which says five commit bodies out of the twenty five most recent. That copy sits on the same
  screen as the default an editor would be retuning, so of the four it is the least likely to be
  left behind, and the two documents in `docs/` remain the pair the entry is really about. Nothing
  registers the numbers in `crosscheck.py` yet, so the argument for leaving them unregistered also
  stands as written. The title says four now; the file name keeps the count it was opened under,
  being an identifier other documents already link to rather than a claim.
