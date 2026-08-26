# Nothing holds the live check roster in the module contract to the suite it describes

**Status:** landed 2026-08-26
**Area:** repo-gates
**Origin:** [ADR-0003](../../adr/ADR-0003-seam-codegen.md)

Opened 2026-08-25 by the pass that rewrote two of those checks
([ADR-0024 host-shape addendum](../../adr/ADR-0024-transport-retry.md)), which found the roster
already drifted: [modules/body-rpc.md](../../modules/body-rpc.md) opened "Two `#[ignore]`d tests run
against a real brain" and then described four, while `body/crates/rpc/tests/live.rs` carried seven.
The count and the list had been wrong through several passes that each added a check and left the
sentence alone.

The live suite is the one suite no gate runs (AGENTS.md gate 3: integration-marked, never in CI,
never under coverage), so its documentation is the only description of it a reader gets without
opening the file, and it is the description that decides whether they run it at all.

**Why it was left.** The roster is prose with a purpose: each bullet says what a check proves and
why it is shaped the way it is, which is exactly what a generated list cannot say. Holding it would
mean comparing the set of `#[ignore]`d `async fn` names in one file against the set of names spelled
in backticks under one heading of one document, which is a narrower question than `crosscheck.py`
answers and a different one from the anchors `backlogcheck.py` resolves. It is a new scan or a new
mode of an existing one, for a document that goes stale on a schedule measured in months.

**What would close it.** A scan holding the two name sets equal, with the prose free to say
whatever it likes about each. The cheapest home is the anchor pass in `backlogcheck.py`, which
already reads documents for the pointers they carry, or a small dedicated scan if that one's
subject should stay pointers. The count in the opening sentence should then be rendered from the
same set or dropped, since a tally restated by hand is the half that drifted first here.

## Trail

- 2026-08-25: opened by the pass that rewrote two of the live checks, which found the roster
  describing four where the suite carried seven.
- 2026-08-26: landed as the
  [ADR-0003 live-roster addendum](../../adr/ADR-0003-seam-codegen.md#addendum-2026-08-26-the-live-roster-is-held-to-the-suite-and-its-tally-is-dropped),
  which built `scripts/rostercheck.py`, a tenth cross-tree scan, with `scripts/rosters.py`
  registering which lists a document keeps, `scripts/rosternames.py` reading what a page names and
  `scripts/rostermembers.py` reading what the tree holds. **Re-derivation moved the entry's
  premise without changing its answer.** The roster was correct on the day this was picked up,
  naming the same eight `#[ignore]`d tests `tests/live.rs` carries, because two passes had
  repaired it by hand since it was filed and neither left anything behind that would catch the
  third divergence. What the entry asked for is what landed: the two name sets held equal, with
  the prose beside each name free to say anything, at any length, in any order. The count was
  **dropped rather than rendered**, which was the entry's own second option and the better one: a
  tally beside a list it summarises is a second copy of the same claim with none of the detail, and
  the sentence that replaced it says the two useful things the number was saying badly. The cheapest
  home the entry proposed, a mode of the anchor pass in `backlogcheck.py`, was **declined** with a
  reason now proved rather than argued: the two gates sit beside each other and each catches what
  the other cannot see, one mutant apiece. The same mechanism closed
  [R-413](413-the-module-contracts-part-list-is-held-by-nobody.md) in the same commit, that entry
  being the same defect at the `scripts/` contract's two lists. What the close opened is filed as
  [R-446](446-the-scan-roster-is-spelled-in-seven-places.md), the list of cross-tree scans itself,
  found already short a scan in one of its seven copies, and
  [R-447](447-a-widened-passage-is-caught-only-by-accident.md), a boundary phrase moved to a wider
  point in its own document.
