# Nothing compares the live check list in the module contract with the suite it describes

**Status:** done 2026-08-26
**Area:** repo-checks
**Origin:** [ADR-0044](../../adr/ADR-0044-document-rosters.md)

[modules/body-rpc.md](../../modules/body-rpc.md) opened "Two `#[ignore]`d tests run against a real
brain" and then described four, while `body/crates/rpc/tests/live.rs` had seven. The count and the
list had been wrong through several passes that each added a check and left the sentence alone.

The live suite is the one suite no check runs (integration-marked, never in CI, never under
coverage), so its documentation is the only description of it a reader gets without opening the
file, and it is what decides whether they run it at all.

The list is prose with a purpose: each entry says what a check proves and why it is shaped the way
it is, which a generated list cannot say. Comparing it means comparing the set of `#[ignore]`d
`async fn` names in one file with the set of names written in backticks under one heading of one
document, which is narrower than what `crosscheck.py` answers and different from the anchors
`backlogcheck.py` resolves. The count in the opening sentence should then be rendered from the same
set or dropped, since a tally restated by hand is the half that came apart first.

## History

- 2026-08-25: opened by the pass that rewrote two of the live checks
  ([ADR-0024](../../adr/ADR-0024-transport-retry.md) decision 24), which found the list describing
  four where the suite had seven.
- 2026-08-26: closed as [ADR-0044 decision 7](../../adr/ADR-0044-document-rosters.md), which built
  `scripts/rostercheck.py`, a tenth cross-tree scan, with `scripts/rosters.py` registering which
  lists a document keeps, `scripts/rosternames.py` reading what a page names and
  `scripts/rostermembers.py` reading what the tree has. Checking again moved the entry's premise
  without changing its answer. The list was correct on the day this was picked up, naming the same
  eight `#[ignore]`d tests `tests/live.rs` has, because two passes had repaired it by hand since it
  was filed and neither left anything behind that would catch the third divergence. What the entry
  asked for is what was built: the two name sets compared as equal, with the prose beside each name
  free to say anything, at any length, in any order. The count was dropped rather than rendered,
  which was the entry's own second option and the better one: a tally beside a list it summarises
  is a second copy of the same claim with none of the detail. The cheapest home the entry proposed,
  a mode of the anchor pass in `backlogcheck.py`, was declined with a reason now proved rather than
  argued: the two scans sit beside each other and each catches what the other cannot see, one
  mutant apiece. The same mechanism closed
  [R-413](413-the-module-contracts-part-list-is-held-by-nobody.md) in the same commit. What the
  close opened is filed as [R-446](446-the-scan-roster-is-spelled-in-seven-places.md), the list of
  cross-tree scans itself, found already short a scan in one of its seven copies, and
  [R-447](447-a-widened-passage-is-caught-only-by-accident.md), a boundary phrase moved to a wider
  point in its own document.
