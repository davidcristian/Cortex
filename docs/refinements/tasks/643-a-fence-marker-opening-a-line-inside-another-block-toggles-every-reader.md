# A fence marker opening a line inside another block toggles every reader

**Status:** done 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0062](../../adr/ADR-0062-shared-check-readers.md)

`markdownfences.is_fence` toggled on any marker at the start of a line. Markdown closes a block only
with a marker of the same character and at least the opening run's length, which is what lets a
four-backtick block contain a three-backtick line as text. Under the old rule that inner line closed
the block, and every line after it was read with the fence state inverted: the anchor scan stops
seeing the headings below it, or starts reading shell comments as headings; the log-sample check
reads a documented line out of prose, or stops reading one inside a block; the commit hook exempts
prose from the wrap, or stops exempting a paste.

This tree already writes the shape the rule was missing.
`docs/adr/ADR-0005-llamacpp-engine.md` opens a four-backtick block because the grammar printed
inside it contains `"```json"`. That inner marker is in the middle of its line, so nothing toggles,
and it is one reflow of that grammar away from the start of a line. A commit
message can nest the same way, though the history has no fenced message at all.

**What closed it.** The shared answer is now `Fences`, a reading of a whole document rather than a
test on one line, and `is_fence` is gone
([ADR-0062](../../adr/ADR-0062-shared-check-readers.md) decision 6). The alternative, a written
argument that a nested block is rare enough and visible enough for the three checks to read it
wrongly, could not be written accurately: two of the directions a wrong reading takes are silent.
A shell comment inside a block read as a heading makes the anchor scan offer an anchor no renderer
offers, so a broken pointer at it passes, and a sample inside a block the log-sample check stops
reading is a documented line nothing compares against its call site.

## History

- 2026-09-12: opened by the close of
  [R-445](445-three-gates-each-spell-the-markdown-fence-for-themselves.md), which gave the three
  document-reading checks one definition of a fence, recorded at
  [ADR-0062](../../adr/ADR-0062-shared-check-readers.md) decision 6. That change was about where the
  definition lived rather than what it said, and all three copies it replaced toggled on the marker,
  so teaching the shared one the closing rule would have put a behaviour change in the same commit
  as a refactor.
- 2026-09-14: still not a live problem, measured rather than argued. Every `.md` file
  `treewalk.walk_files` returns was read line by line under markdown's own closing rule: no marker
  at the start of a line falls inside another block anywhere in this tree.
  `docs/adr/ADR-0005-llamacpp-engine.md` opens a four-backtick block at line 1630 and closes it at
  1634, and the `"```json"` inside it sits at line 1631 with the marker in the middle of the line.
- 2026-09-15: done. The search was run once more over all 764 `.md` files, with the same result, so
  the change moves no answer about anything committed here.
