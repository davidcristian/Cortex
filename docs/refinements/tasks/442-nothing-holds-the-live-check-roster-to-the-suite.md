# Nothing holds the live check roster in the module contract to the suite it describes

**Status:** open, fix when it bites
**Trigger:** a live check is added, renamed or removed and the module contract keeps describing the
set that ran before it, which is when a reader picking the suite up is told the wrong thing.
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
