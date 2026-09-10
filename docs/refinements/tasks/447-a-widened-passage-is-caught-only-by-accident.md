# A roster's passage widened past the list it bounds is caught only by accident

**Status:** open, fix when it bites
**Trigger:** a boundary phrase is edited to a point past the list it bounds and the wider passage
happens to carry no name, at which point the roster silently compares a bigger region than the
one it describes.
**Area:** repo-gates
**Origin:** [ADR-0003](../../adr/ADR-0003-seam-codegen.md)
**Verified:** 2026-09-11

Opened 2026-08-26 by the close of
[R-442](442-nothing-holds-the-live-check-roster-to-the-suite.md), which made a roster's boundaries
data and held the phrases to appearing exactly once, and nothing else about them.

`scripts/rosters.py` bounds each passage with two phrases the document carries. A phrase that
stops appearing, or starts appearing twice, is a reported fault. A phrase **moved** is not a fault at
all: it still appears once, so the gate reads a different region and compares whatever it finds
there.

Measured rather than reasoned about, on the day this was filed. Moving the live seam roster's
closing phrase to the invariants heading below it made the passage cover a section whose bullets
open with prose, and the run died on those, which is the accident working. Moving the module
roster's closing phrase back one sentence, from the start of the first bullet to a phrase inside
it, covered a run of text carrying no code span the module pattern matches, and
`rostercheck.py` exited 0 with the same summary line it prints when nothing moved.

The exposure is small and asymmetric: a widened passage can only make the gate see MORE names,
which fails on any name that is not a member, and can never hide a member the roster lost. What it
can do is make the passage's own claim untrue while the verdict stays green, so a later reader
trusts a boundary that no longer bounds the list.

**Why it was left.** Every fix costs something real. Requiring a passage to carry at least one
name catches nothing here, since a widened passage still carries all of them. Pinning the
passage's length or its line span would make an ordinary prose edit fail the gate, which is what
the whole design avoids. Reading the roster's extent from the document's own structure is the
heading-and-paragraph approach the close argued its way out of, since two rosters share one
paragraph's page and one opens with a fenced command.

**What would close it.** Probably a registry-health test rather than a gate rule: assert that each
passage is the smallest run containing all of its names, which is checkable without asserting any
number, and which a widened boundary breaks by definition. Check first whether that is true of the
registered passages: measured on 2026-09-11 over all eight, it is true of none, since every one
deliberately opens or closes some distance from its nearest name.

## Trail

- 2026-09-11: not fired. No `opens` or `closes` phrase registered in `scripts/rosters.py` has
  been edited since the day this was filed: the registry's history since then adds five rosters
  and moves no phrase, and `rostercheck` passes today over 8 rosters in 5 documents naming 196
  members. The registry-health test proposed above was measured against every registered passage
  rather than the three named when this was written, and none of the eight is the smallest run
  containing its names. Each carries prose before its first name, from 29 characters on the
  registry's parts to 1132 on the live seam checks, and after its last, from 3 to 409, so the
  test would fail every roster as it stands and cannot close this without a looser bound.
