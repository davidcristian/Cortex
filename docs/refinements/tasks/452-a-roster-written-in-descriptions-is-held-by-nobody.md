# A roster written in descriptions rather than names is held by nobody

**Status:** landed 2026-09-11
**Area:** repo-gates
**Origin:** [ADR-0003](../../adr/ADR-0003-seam-codegen.md)

Opened 2026-08-26 by the close of
[R-446](446-the-scan-roster-is-spelled-in-seven-places.md), which held the three copies of the
cross-tree scan list that spell module names and left the two that spell phrases.

Two passages describe the cross-tree scans without naming one of them. The header comment of
`.github/workflows/ci.yml` runs through them as "the 300-line cap, the punctuating-dash ban, the
cross-language constant check" and so on, and the Purpose paragraph of
[modules/repo-gates.md](../../modules/repo-gates.md) does the same in its own words. Both were
complete the day this was filed. The workflow header is the copy that was found listing eight
scans on a day nine had been running, which is the drift the whole roster mechanism exists to
catch, and it is the one copy of the list the mechanism still cannot see. It was filed as waiting
for the next scan to be added, and that happened the next day: the flag check landed on
2026-08-27, the Purpose paragraph picked it up, and the header kept running through ten scans
while eleven ran, until this entry was read on 2026-09-11.

**Why it was left.** The roster reader holds names, and these passages carry none. The only way to
hold them with what exists is to rewrite both into lists of file names, and that trade is bad in
both places: the Purpose paragraph's job is to say what this tree is, which is a sentence about
gates rather than a list of files, and the next paragraph already names every module. The workflow
header's job is to say why these scans are exempt from the path filter, which is an argument and
not an inventory.

**What would close it.** Either a roster whose members are read as descriptions, which needs a
registered phrase per member and is a second hand-written list holding the first, or a decision
that a description is not a roster, with the reason written down and the two passages left as
prose that a reader is expected to check by eye. The second is probably right and is not obviously
right, which is why this is recorded rather than settled: a description carrying a claim about
membership is still making the claim, and the last time one of these went stale nobody noticed for
a day.

## Trail

- 2026-08-26: opened by the close of
  [R-446](446-the-scan-roster-is-spelled-in-seven-places.md), which held the three copies spelling
  names and argued the tallies away under the standing decision, leaving these two. Recorded under
  what the ADR-0003 scan-roster addendum defers.
- 2026-09-11: **the trigger fired on 2026-08-27, the day after this was filed, and nobody read it
  as a firing.** The change that added `flagcheck.py` edited the workflow's held roster comment,
  the Purpose paragraph of the gate tree's contract and AGENTS.md, and left the workflow header
  running through ten scans. It stayed that way for fifteen days through every gate run, which
  is the exposure this entry describes. The header is repaired in this pass so it reads true
  today, and the entry is re-filed as actionable: the decision it defers, a roster read as
  descriptions or a written reason that a description is not one, now has a measured cost to
  weigh. Recorded in the ADR-0003 addendum of this date.
- 2026-09-11: landed, by neither of the two closures named above. A description is not a roster:
  holding one means a registered phrase per member per document, which pins a sentence's wording
  in the registry, and the two passages spell the same scans differently. The workflow header's
  inventory was a restatement of the held roster sixty lines below it in the same file, and it
  was the copy that drifted both times, so it is removed and the header now says where the list
  is and what holds it. The Purpose paragraph of the gate tree's contract stays as prose, left to
  the eye and recorded as such, since it is what a purpose paragraph is for and sits in the file
  every scan addition edits twice; the residual is filed as
  [R-631](631-the-purpose-paragraph-describes-the-scans-by-eye.md). Recorded in the origin
  decision's addendum of the same day, the later of the two.
