# The write run judges the links of the index it replaces

**Status:** landed 2026-09-11
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
- 2026-09-11: landed. Re-derived first by running the sequence above in a scratch backlog, which
  showed a second face the entry did not name: the write run that rendered the trigger's link into
  the index exited 0, and the write run that removed it exited 1 while writing the corrected
  index, so both verdicts were about the file on disk before the rewrite rather than the file
  left behind. `check_links` in `scripts/backlogcheck.py` now takes each source as a path with the
  text judged as that document, and `run_one` hands it the task files' own text before the splice
  and the spliced index after it, the rule the anchor half already followed.
  `test_main_judges_the_index_links_on_the_text_the_write_run_puts_on_disk` pins the pair of runs
  and fails on the old ordering in both directions. The mutation table, with counts over
  `scripts/tests`, is in the origin decision's addendum of the same day, which also decides the
  question set aside above: a link in a `Trigger` stays allowed, and the gate answers it by
  reporting the index's link on the run that renders it.
