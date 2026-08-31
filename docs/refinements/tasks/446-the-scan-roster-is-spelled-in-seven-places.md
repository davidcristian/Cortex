# The list of cross-tree scans is spelled in seven places and held in none

**Status:** landed 2026-08-26
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

## Trail

- 2026-08-26: opened by the close of
  [R-442](442-nothing-holds-the-live-check-roster-to-the-suite.md), which built the roster gate and
  registered three lists, none of them this one.
- 2026-08-26: landed as the
  [ADR-0003 scan-roster addendum](../../adr/ADR-0003-seam-codegen.md#addendum-2026-08-26-the-scan-roster-is-held-to-the-recipes-that-run-it),
  which built `scripts/scanrecipes.py` to answer what the cross-tree scans really are and
  registered the three copies that spell names. **Re-derivation moved the premise twice.** There
  are eight copies rather than seven, and the eighth is the one that was stale: the module-doc line
  in [docs/index.md](../../index.md), which this entry did not count, named eight of the ten scans,
  missing `defaultcheck.py` and `backlogcheck.py`, and called `backlogcheck.py` the fifth
  cross-tree scan when it is the tenth. It is repaired here. The entry's guess that the README row
  was probably holdable is wrong in the other direction: that row names nothing at all and carries
  only a tally.
- 2026-08-26: what the copies are, since the entry treated them as one kind of thing. Three spell
  names and are now held, the gate list in [AGENTS.md](../../../AGENTS.md), the `cross-tree` job
  comment in `.github/workflows/ci.yml` and the documentation index line. **A comment is a roster
  when it names its members**, which is the question this entry left open, and it needed no reader
  that understands YAML: the boundary phrases do the work a parser would, and the bare spelling
  reaches a comment for the same reason it reaches a repo map. Three copies carry only a tally,
  the README row, the justfile comment and the repo map's justfile line, and stay unheld under the
  standing decision that a document's numbers are its own business. Two describe the scans in
  phrases rather than naming them, and holding those would mean rewriting each passage into a list
  of file names, which costs the Purpose paragraph the thing it is for; that residue is filed as
  [R-452](452-a-roster-written-in-descriptions-is-held-by-nobody.md), and it matters because the
  descriptive copy in the workflow header is exactly the one that went stale before this entry was
  written.
- 2026-08-26: the far side is the part the entry called honestly hard, and it is answered the way
  the entry proposed. A cross-tree scan is not a file, so the members are read from the two files
  that run one: the unbroken run of `just check-*` lines the `check` recipe opens with, and every
  step of CI's `cross-tree` job, resolved to a module through each recipe's own body since
  `check-backlog` runs `backlogcheck.py`. The two must agree or the reader exits rather than
  answering, which makes a scan wired into one file and not the other an exit 2 naming both lists
  rather than a half answer nothing reports.
