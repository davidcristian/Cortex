# A counted mention that finds nothing gets none of the reading a presence check gets

**Status:** landed 2026-09-12
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

Opened 2026-08-23 by the close of
[R-403](403-a-needles-literal-reddens-the-wrong-entry.md), which made an unfound needle's
fault name whose literal stopped matching, and wired that into one of the two branches that can
find nothing.

`scripts/crosscheck.py`'s `check_mention` splits on whether the mention pins an occurrence count. A
mention without one raises through `needles.unfound`, which says whether the file still spells the
constant's own value and how much of the needle it carries. A mention **with** one raises the older
sentence, "found 0, pinned 2; move the whole set, or correct occurrences in the registry", which is
true and says nothing about which of the needle's literals moved. Zero found is exactly the case
the reading was written for, and there are counted mentions over needles carrying several of a
neighbour's digits: `docs/runbooks/body-volume.md`'s `host.docker.internal:{value}` and
`CORTEX_BODY_ADDR=0.0.0.0:{value}` are both pinned at two occurrences
(`scripts/endpointcouplings.py`).

**Why it was left.** Scope, and a real trade. The counted branch's message is asserted verbatim by
the whole-spelling suite (`scripts/tests/test_crosscheck.py` pins "as a token of its own: found 0,
pinned 2"), so the change is a message edit plus a test edit plus a branch, in a close whose
subject was the presence check. Nothing in the tree is waiting on it: no counted mention has ever
gone to zero on the real tree.

**What would close it.** Guard the count message on `found` and hand a zero to `needles.unfound`,
keeping the pinned count as a trailing clause so the reader still sees that the mention was counted.
The care it needs is that the two facts must not be run together into a sentence claiming the
needle was found some number of times when it was found none: the count is what the registry asked
for, and zero is what the file said. A branch there needs a test that drives it, and the suite
already builds a counted mention that finds nothing.

**Landed 2026-09-12 off its trigger, as the shape above, and both halves of the description held
against the code.** `check_mention` now tests `found` before it tests the count, so a file holding
none of the needle gets `needles.unfound` whether or not a count is pinned, and the count follows
as its own clause, `the registry pins 2 occurrences, so move the whole set, or correct occurrences
in the registry`. No sentence states a number of occurrences the file did not hold. A count that is
wrong without being zero still gets `found N, pinned M`, which is the one reading a run and a
still-spelled value cannot improve on: the needle is there and the question is how many. The advice
both faults end on is now one string, `crosscheck.RECOUNT`, rather than two spellings of one
sentence.

**The trigger had still not fired, and it was not waited for.** The trade the entry recorded turned
out to be smaller than it reads: one branch, one shared constant, one suite assertion re-aimed from
the count sentence to the reading, and one test written to drive the new branch. Four drifts planted
on the real tree before and after the change, tabled in the ADR-0023 counted-zero addendum, two of
them a counted mention losing its whole set and two controls, the short count and an uncounted
mention, both unchanged.

## Trail

- 2026-09-10: read against the tree and still not fired. `check_mention` still splits on
  `wanted is None`, still sends only the uncounted branch through `needles.unfound`, and the
  counted branch still raises the sentence this entry quotes, with no reading of which literal
  moved. The two counted mentions over `docs/runbooks/body-volume.md` are still pinned at two
  occurrences in `scripts/endpointcouplings.py`, and three more counted mentions sit beside them
  there. Nothing has gone to zero: `crosscheck` passed today over 91 constants, 109 declaring
  sites and 296 mentions, 25 of them pinned to a count.
- 2026-09-12: landed off the trigger, which has still not fired. `check_mention` tests `found`
  before the count, so zero reaches `needles.unfound` either way and the pinned count trails it as
  its own clause; the two faults share one spelling of what a wrong count asks of a reader. Four
  drifts planted on the real tree before and after, over the registry's own body port: both of the
  volume runbook's endpoint spellings moved and both of its export spellings moved each turned the
  bare count sentence into the run, the still-spelled value and its line, while the short count and
  an uncounted mention printed what they printed before. Tabled in the ADR-0023 counted-zero
  addendum. One residue opened, the short count naming no line
  ([R-656](656-a-short-count-names-no-line.md)), which this change made the asymmetry it is.
