# The registry holds every place it names, and nothing says it names every place

**Status:** declined 2026-08-23
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-23 by the close of
[R-389](389-the-brain-port-is-held-in-code-and-not-in-prose.md), the third prose sort in a row
whose own count of the tree was wrong, and wrong in the same direction.

`crosscheck.py` answers one question well: every place the registry names still spells the same
value. It cannot answer the other one. A value spelled somewhere no needle reaches is invisible to
it, and the invisibility is silent, which is the property that makes a survey the only way to find
one. Three surveys have now paid for that by hand:

- The legibility pair was surveyed as five loose sites in three documents and turned out to be 49
  spellings in 14 files, three of the files being ones the entry never named at all.
- The body's bind port was surveyed by document, and counting spellings instead found eight more
  inside files that already carried a row, one runbook alone spelling it six times behind a single
  presence check.
- The brain's seam port was surveyed as a prose gap and turned out to be a third code, including a
  `Dockerfile`'s `EXPOSE`, a tonic client's dial example and two live suites' fallbacks.

Every one of those was found by a person grepping, and every one of them was reported as a
correction to the entry that had asked. That is not a run of bad entries; it is what happens when
the only reading of coverage is somebody's memory of the tree.

**Why it was left.** It is a second question rather than a wider version of the first, and the two
have different failure modes. The scan is `--root`-driven, fails closed, and reports faults. A
coverage reading would walk the whole tree looking for occurrences of an already agreed value, and
most of what it found would be legitimate: an ADR recording a decision, a measured arm, a captured
log line, a suite that holds itself, a number that means something else entirely. So its output is
a **report** and not a fault, and the design question is what turns a listing nobody reads into
something that can gate. That is a decision, not a row, and it does not belong inside a close about
one port.

**What would close it.** Decide the shape first. The cheap end is a `--survey` mode printing every
occurrence of each registered value that no needle covers, run by hand when an entry is being
sorted, which would have turned all three surveys above from grepping into reading. The expensive
end is a gate: an acknowledged-exclusions list per entry, so a new unregistered spelling fails and
a known one does not, which is a real registry field and a real maintenance cost. Read the false
positive rate before choosing, since it decides everything: a measurement over the current registry
would say how much of the tree a survey would print, and the same reading exists already in the
population scan the second-spelling entry ran
([R-387](387-a-second-spelling-shares-a-held-line.md)), which found six of its eleven hits were
artefacts of the reading rather than defects. If the ratio is that bad at the whole-tree scale, the
report is the answer and the gate is not.

## Trail

- 2026-08-23: opened by the close of
  [R-389](389-the-brain-port-is-held-in-code-and-not-in-prose.md), the third sort whose count the
  tree corrected upward, after the legibility pair's and the body port's.
- 2026-08-23: declined, on the measurement the entry itself asked for first. Both honest candidate
  sets were run over the 61 entries against every tracked text file. Rendering each registered value
  and counting its bounded occurrences returns **37,717** that no needle covers, because the deep
  tier's logical id is the word `brain` (3,799 hits), the resident tier's is `cortex` (3,281) and
  four entries are the number `2`. Narrowing candidates to files that also spell the constant's own
  identifier returns **927**, of which 34 belong to the brain's bind host, an entry that had been
  sorted exhaustively an hour earlier and whose true far sides are three. So a gate would need an
  acknowledged-exclusions list of either size, a second registry nobody maintains, and a report at
  either rate is the listing nobody reads that this entry named as its own failure mode, with the
  added cost that it would let a sort claim it had been checked. **The entry's premise survives and
  its remedy does not**: a value spelled where no needle reaches is still invisible, and what the
  measurement settles is that the invisibility is lifted by sorting rather than by counting. The
  method is recorded in [repo-gates.md](../../modules/repo-gates.md) instead: sort by the name a
  value is spelled under, never by its digits, then read each hit against the tense test, which is
  the judgement no scan makes and the one a census would have to make 927 times. The one scoping
  that did measure well, leftover occurrences on lines a needle already matched, is the
  second-spelling reading, which closed its own population. Tabled in the ADR-0029 census addendum.
  One residue filed: the registry's own shape is stated by hand in every addendum and goes stale
  ([R-404](404-the-registrys-own-shape-is-counted-by-hand.md)).
