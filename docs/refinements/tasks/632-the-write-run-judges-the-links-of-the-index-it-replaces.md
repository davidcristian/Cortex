# The write run checks the links of the index it replaces

**Status:** done 2026-09-11
**Area:** repo-checks
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

`run_one` in `scripts/backlogcheck.py` called `check_links(root, tasks, index)` before it rendered,
and `check_links` read the index as it sat on disk. On a `--write` run that text is the index the
run is about to replace, so a broken link in the generated block, one the fresh rendering no longer
has, was reported, the exit code was 1, and the fresh index was written anyway. The next
`just check-backlog` then passed over the file the write had left behind, so two runs disagreed
about the same tree.

The anchor half already worked the other way: `run_one` hands `backloganchors.anchors(wanted)` the
spliced text, so a stale index is checked as the document it is about to become. The path half of
the same link had never been moved onto that rule.

**How it was seen.** A task file was written with a markdown link inside its `Trigger` field,
relative to the task file's depth. The index renders a trigger verbatim, so the link broke at the
index's depth and `just backlog` correctly reported it. The trigger was rewritten without the link
and `just backlog` run again: it reported the same broken link, read out of the index the previous
run had written, exited 1, and wrote the corrected index. `just check-backlog` passed immediately
after, and a second `just backlog` exited 0.

**What closed it.** `check_links` now takes each source as a path with the text checked as that
document, and `run_one` hands it the task files' own text before the splice and the spliced index
after it.

## History

- 2026-09-11: opened after the sequence above, during the slot that finished the entry about a
  roster written in descriptions.
- 2026-09-11: done. Checked first by running the sequence above in a scratch backlog, which showed
  a second side the entry did not name: the write run that rendered the trigger's link into the
  index exited 0, and the write run that removed it exited 1 while writing the corrected index, so
  both results were about the file on disk before the rewrite rather than the file left behind.
  `test_main_judges_the_index_links_on_the_text_the_write_run_puts_on_disk` asserts the pair of runs
  and fails on the old ordering in both directions. The mutation table, with counts over
  `scripts/tests`, is in the commit. [ADR-0039](../../adr/ADR-0039-backlog-per-task.md) decision 13
  settles the question set aside here, whether a `Trigger` may contain a markdown link at all given
  that the field renders at a depth its author did not write it for: it stays allowed, and the check
  reports the index's link on the run that renders it.
