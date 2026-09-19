# The list of cross-tree scans is written in seven places and checked in none

**Status:** done 2026-08-26
**Area:** repo-checks
**Origin:** [ADR-0044](../../adr/ADR-0044-document-rosters.md)

The cross-tree scans are named as a set in seven places: the check list in
[AGENTS.md](../../../AGENTS.md), the `scripts/` line of its repo map, the `just check` table row in
[README.md](../../../README.md), the comment above the `check` recipe in the justfile, the header
comment and the `cross-tree` job comment in `.github/workflows/ci.yml`, and the Purpose paragraph
of [modules/repo-checks.md](../../modules/repo-checks.md). Four of them also have a count. Every one
is written by hand.

One was already wrong. The header comment in `.github/workflows/ci.yml` listed eight scans on the
day a ninth had been running for a day, having never picked up the documented-log sample check, and
the omission was found only because the list work was editing the sentence next to it.

The mechanism that would check it reads a document against a set the tree really has, and a scan is
not a file on disk: what makes something a cross-tree scan is a `check-*` recipe in the justfile
that CI's `cross-tree` job also runs, which is two files in two languages this reader parses
neither of. Three of the seven copies are also not prose but comments inside YAML and inside a
justfile, and one is a table cell.

## History

- 2026-08-26: opened by the close of
  [R-442](442-nothing-holds-the-live-check-roster-to-the-suite.md), which built the list-checking
  scan and registered three lists, none of them this one.
- 2026-08-26: closed as [ADR-0044 decisions 10 and 11](../../adr/ADR-0044-document-rosters.md),
  which built `scripts/scanrecipes.py` to answer what the cross-tree scans really are and
  registered the three copies that name modules. Checking again moved the premise twice. There are
  eight copies rather than seven, and the eighth was the stale one: the module-doc line in
  [docs/index.md](../../index.md), which this entry did not count, named eight of the ten scans,
  missing `defaultcheck.py` and `backlogcheck.py`, and called `backlogcheck.py` the fifth
  cross-tree scan when it is the tenth. It is repaired. The entry's guess that the README row was
  probably checkable is wrong in the other direction: that row names nothing at all and has only a
  tally.
- 2026-08-26: what the copies are, since the entry treated them as one kind of thing. Three name
  modules and are now checked: the check list in [AGENTS.md](../../../AGENTS.md), the `cross-tree`
  job comment in `.github/workflows/ci.yml` and the documentation index line. A comment is a list
  when it names its members, which is the question this entry left open, and it needed no reader
  that understands YAML: the boundary phrases do the work a parser would. Three copies have only a
  tally, the README row, the justfile comment and the repo map's justfile line, and stay unchecked
  under the decision that a document's numbers are its own business. Two describe the scans in
  phrases rather than naming them, and checking those would mean rewriting each passage into a list
  of file names, which costs the Purpose paragraph the thing it is for; that residue is filed as
  [R-452](452-a-roster-written-in-descriptions-is-held-by-nobody.md), and it matters because the
  descriptive copy in the workflow header is the one that went stale before this entry was written.
- 2026-08-26: the set the copies are compared with is answered the way the entry proposed. A
  cross-tree scan is not a file, so the members are read from the two files that run one: the
  unbroken run of `just check-*` lines the `check` recipe opens with, and every step of CI's
  `cross-tree` job, resolved to a module through each recipe's own body since `check-backlog` runs
  `backlogcheck.py`. The two must agree or the reader exits rather than answering, so a scan wired
  into one file and not the other is an exit 2 naming both lists.
