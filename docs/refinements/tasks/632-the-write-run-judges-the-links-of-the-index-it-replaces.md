# The write run judges the links of the index it replaces

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

Opened 2026-09-11 by a slot that watched it happen. `run_one` in `scripts/backlogcheck.py` calls
`check_links(root, tasks, index)` before it renders, and `check_links` reads the index as it sits on
disk. On a `--write` run that text is the index the run is about to replace, so a link problem in
the generated block, one that the fresh rendering no longer carries, is reported, the exit code is
1, and the fresh index is written anyway. The next `just check-backlog` then passes over the file
the write left behind, and the two verdicts disagree about the same tree.

The anchor half already answers the other way. `run_one` hands `backloganchors.anchors(wanted)` the
spliced text, and the repo-wide anchor addendum says why: a stale index is judged as the document
it is about to become. The path half of the same link was never moved onto that rule.

**How it was seen.** A task file was written with a markdown link inside its `Trigger` field,
relative to the task file's depth. The index renders a trigger verbatim, so the link broke at the
index's depth, and `just backlog` correctly reported it. The trigger was rewritten without the
link and `just backlog` run again: it reported the same broken link, read out of the index the
previous run had written, exited 1, and wrote the corrected index; `just check-backlog` passed
immediately after. A second `just backlog` exited 0.

**What would close it.** Run the index's link check over `wanted`, the spliced text, rather than
over the file on disk, so both halves of a link are judged against the document the run writes.
The task files' own links are read off disk and stay so, since nothing rewrites them. A test in
`scripts/tests/test_backlogcheck.py` that writes a task whose trigger carries a link resolvable
from the task file and not from the index, runs with `--write` twice, and asserts the second run
exits 0 and the first reports the link once, pins it.

A second question sits beside it and is not this entry: whether a `Trigger` may carry a markdown
link at all, given that the field renders at a depth its author did not write it for. Today the
gate answers by reporting the index's broken link, which is loud, and naming the document in a
code span is the working form.

## Trail

- 2026-09-11: opened after the sequence above, during the slot that landed the entry about a
  roster written in descriptions. Recorded in the origin decision's addendum of the same day.
