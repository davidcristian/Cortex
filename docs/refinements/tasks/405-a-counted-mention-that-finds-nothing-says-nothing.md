# A counted mention that finds nothing gets none of the reading a presence check gets

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** A mention pinning an occurrence count going to zero found, which is a counted
far side losing every one of its occurrences at once rather than one of them.

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
