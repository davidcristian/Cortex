# The list of cross-tree scans is spelled in seven places and held in none

**Status:** open, fix when it bites
**Trigger:** a scan is added, renamed or removed and one of the seven copies keeps describing the
set that ran before it, which has already happened once and cost a reader the knowledge that a
gate exists.
**Area:** repo-gates
**Origin:** [ADR-0003](../../adr/ADR-0003-seam-codegen.md)

Opened 2026-08-26 by the close of
[R-442](442-nothing-holds-the-live-check-roster-to-the-suite.md), which built a gate holding a
document's roster to the set it describes and registered three rosters, none of them this one.

The cross-tree scans are named as a set in seven places: the gate list in
[AGENTS.md](../../../AGENTS.md), the `scripts/` line of its repo map, the `just check` table row
in [README.md](../../../README.md), the comment above the `check` recipe in the justfile, the
header comment and the `cross-tree` job comment in `.github/workflows/ci.yml`, and the Purpose
paragraph of [modules/repo-gates.md](../../modules/repo-gates.md). Four of them also carry a
count. Every one is written by hand.

One of them was already wrong. The header comment in `.github/workflows/ci.yml` listed eight
scans on the day a ninth had been running for a day, having never picked up the documented-log
sample check, and the omission was found only because the roster work was editing the sentence
next to it. It was corrected in the same commit that opened this entry.

**Why it was left.** The gate that would hold it exists now and reads a **document** against a set
the tree really holds. A scan is not a file on disk: what makes something a cross-tree scan is a
`check-*` recipe in the justfile that CI's `cross-tree` job also runs, which is two files that are
neither of them a directory listing, in two languages the reader here parses neither of. Three of
the seven copies are also not prose, they are comments inside YAML and inside a justfile, and one
is a table cell.

**What would close it.** A reader that answers what the cross-tree scans are, which is most
honestly the recipes the `cross-tree` job runs, plus rosters over the copies whose shape the
existing name reader can already handle, which is the two in AGENTS.md, the one in
[modules/repo-gates.md](../../modules/repo-gates.md) and probably the README row. The comments in
the workflow and the justfile need either a reader that finds a roster inside a comment block or a
decision that a comment is not a roster. Decide the counts separately: four of these copies say a
number, and the standing decision is that a document's tallies are its own business.
