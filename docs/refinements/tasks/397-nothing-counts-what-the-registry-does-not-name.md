# The registry checks every place it names, and nothing says it names every place

**Status:** declined 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`crosscheck.py` answers one question well: every place the registry names still writes the same
value. It cannot answer the other one. A value written somewhere no search text reaches is
invisible to it, and nothing reports the omission, so a survey by hand is the only way to find one.
Three surveys paid for that:

- The legibility pair was described as five loose places in three documents and turned out to be 49
  occurrences in 14 files, three of the files never named in the entry.
- The body's bind port was surveyed by document, and counting occurrences instead found eight more
  inside files that already had a row, one runbook alone writing it six times behind a single
  presence test.
- The brain's port was described as a prose gap and turned out to be a third code, including a
  `Dockerfile`'s `EXPOSE`, a tonic client's dial example and two live suites' fallbacks.

Each was found by a person grepping, and each was reported as a correction to the entry that had
asked. The only reading of coverage available was somebody's memory of the tree.

This is a second question rather than a wider version of the first. The scan is `--root`-driven,
fails closed, and reports faults. A coverage reading would walk the whole tree looking for
occurrences of an already agreed value, and most of what it found would be legitimate: an ADR
recording a decision, a measured variant, a captured log line, a suite that checks itself, a number
that means something else. So its output is a report and not a fault, and the design question is
what turns a listing nobody reads into something that can fail a build.

## History

- 2026-08-23: opened by the close of
  [R-389](389-the-brain-port-is-held-in-code-and-not-in-prose.md), the third sorting whose count
  the tree corrected upward, after the legibility pair's and the body port's.
- 2026-08-23: declined, on the measurement the entry itself asked for. Both candidate sets were run
  over the 61 entries against every tracked text file. Rendering each registered value and counting
  its bounded occurrences returns 37,717 that no search text covers, because the deep tier's
  logical id is the word `brain` (3,799 hits), the resident tier's is `cortex` (3,281) and four
  entries are the number `2`. Narrowing candidates to files that also write the constant's own
  identifier returns 927, of which 34 belong to the brain's bind host, an entry that had been
  sorted exhaustively an hour earlier and whose true count is three. So a check would need an
  exclusions list of either size, a second registry nobody maintains, and a report at either rate
  is the listing nobody reads, with the added cost that it would let a sorting claim it had been
  checked. The entry's premise survives and its remedy does not: a value written where no search
  text reaches is still invisible, and the measurement settles that the invisibility is lifted by
  sorting rather than by counting. The method is recorded in
  [repo-checks.md](../../modules/repo-checks.md) instead: sort by the name a value is written
  under, never by its digits, then read each hit against the test of whether the sentence becomes
  wrong or becomes a record of the past, which is the judgement no scan makes and the one a census
  would have to make 927 times. The one scoping that did measure well, leftover occurrences on
  lines a search text already matched, is the second-occurrence reading, which closed its own
  population. One residue filed: the registry's own shape is stated by hand in every record and
  goes stale ([R-404](404-the-registrys-own-shape-is-counted-by-hand.md)).
