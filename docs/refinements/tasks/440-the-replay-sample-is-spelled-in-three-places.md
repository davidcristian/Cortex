# The replay sample and its window are spelled in three places

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** a change to either number, since the copies drift the moment one of them moves.

Opened 2026-08-25 by the pass that gave the replay a cadence
([R-357](357-a-replay-pass-has-no-cadence.md), [ADR-0002 replay-cadence
addendum](../../adr/ADR-0002-toolchain-gates.md)). Two numbers decide that pass, the sample of five
and the window of twenty five, and each is written three times: as a default parameter of the
`replay` recipe in the `justfile`, in the prose of
[docs/runbooks/mutation-replay.md](../../runbooks/mutation-replay.md), and in the addendum that
decided them. The recipe is the executable copy and the other two are the argument for it, so a
retuned default leaves two documents stating a rule the tool no longer follows.

**Why no coupling was registered on the spot.** `crosscheck.py` ties a value only where its
registry names both sides, and both far sides here are prose spelling the numbers as words rather
than digits, which is the kind of mention that registry reads through a needle rather than a
literal. Registering it is a registry entry plus its tests plus a needle that survives a sentence
being rewritten around it, which is more machinery than a number nobody has yet had a reason to
change. The precedent for leaving it alone is the four shuffle seeds, deliberately unregistered,
though that argument is the opposite of this one: those are four independent values that must not
be tied, while these are one value each, spelled three times.

**What would close it.** Either a registered coupling holding the recipe's defaults against the
sentences that state them, or a decision that the prose stops naming the numbers and points at the
recipe for them, which costs the addendum its argument and is probably the wrong trade.
