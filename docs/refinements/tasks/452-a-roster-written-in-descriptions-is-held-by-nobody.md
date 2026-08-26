# A roster written in descriptions rather than names is held by nobody

**Status:** open, fix when it bites
**Trigger:** a cross-tree scan is added and one of the two descriptive passages keeps running
through the set that ran before it, which is what happened the last time one was added and cost a
reader the knowledge that a gate exists.
**Area:** repo-gates
**Origin:** [ADR-0003](../../adr/ADR-0003-seam-codegen.md)

Opened 2026-08-26 by the close of
[R-446](446-the-scan-roster-is-spelled-in-seven-places.md), which held the three copies of the
cross-tree scan list that spell module names and left the two that spell phrases.

Two passages describe the same ten scans without naming one of them. The header comment of
`.github/workflows/ci.yml` runs through them as "the 300-line cap, the punctuating-dash ban, the
cross-language constant check" and so on, and the Purpose paragraph of
[modules/repo-gates.md](../../modules/repo-gates.md) does the same in its own words. Both are
complete today. The workflow header is the copy that was found listing eight scans on a day nine
had been running, which is the drift the whole roster mechanism exists to catch, and it is the one
copy of the list the mechanism still cannot see.

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
