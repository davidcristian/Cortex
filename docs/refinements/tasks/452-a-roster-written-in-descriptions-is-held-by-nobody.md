# A list written in descriptions rather than names is checked by nobody

**Status:** done 2026-09-11
**Area:** repo-checks
**Origin:** [ADR-0044](../../adr/ADR-0044-document-rosters.md)

Two passages describe the cross-tree scans without naming one of them. The header comment of
`.github/workflows/ci.yml` runs through them as "the 300-line cap, the punctuating-dash ban, the
cross-language constant check" and so on, and the Purpose paragraph of
[modules/repo-checks.md](../../modules/repo-checks.md) does the same in its own words. Both were
complete the day this was filed. The workflow header is the copy that was found listing eight scans
on a day nine had been running, which is the drift the whole list mechanism exists to catch, and it
is the one copy the mechanism still cannot see.

The reader compares names, and these passages have none. The only way to check them with what
exists is to rewrite both into lists of file names, and that trade is bad in both places: the
Purpose paragraph's job is to say what this tree is, and the next paragraph already names every
module; the workflow header's job is to say why these scans are exempt from the path filter, which
is an argument and not an inventory.

## History

- 2026-08-26: opened by the close of
  [R-446](446-the-list-of-cross-tree-scans-is-written-in-seven-places.md), which checked the three copies that
  name modules and argued the tallies away, leaving these two. Recorded as what ADR-0044 decision
  11 leaves unchecked.
- 2026-09-11: the trigger fired on 2026-08-27, the day after this was filed, and nobody read it as
  a firing. The change that added `flagcheck.py` edited the workflow's checked comment, the Purpose
  paragraph of the check tree's contract and AGENTS.md, and left the workflow header running
  through ten scans. It stayed that way for fifteen days through every check run, which is the
  exposure this entry describes. The header is repaired in this pass, and the entry is re-filed as
  actionable: the decision it defers now has a measured cost to weigh.
- 2026-09-11: closed, by neither of the two options named above. A description is not a list:
  checking one means a registered phrase per member per document, which fixes a sentence's wording
  in the registry, and the two passages describe the same scans differently. The workflow header's
  inventory was a restatement of the checked list sixty lines below it in the same file, and it was
  the copy that went stale both times, so it is removed and the header now says where the list is
  and what checks it. The Purpose paragraph of the check tree's contract stays as prose, left to
  the eye and recorded as such, since it is what a purpose paragraph is for and sits in the file
  every scan addition edits twice; the residue is filed as
  [R-631](631-the-purpose-paragraph-describes-the-scans-by-eye.md). Recorded as the origin
  decision's decision 12.
