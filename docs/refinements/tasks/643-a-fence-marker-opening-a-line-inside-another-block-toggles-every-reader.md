# A fence marker opening a line inside another block toggles every reader

**Status:** landed 2026-09-15
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-09-12 by the close of
[R-445](445-three-gates-each-spell-the-markdown-fence-for-themselves.md), which gave the three
document-reading gates one answer to what a fence is and made the reading behind it visible in one
place.

`markdownfences.is_fence` toggles on any marker at the start of a line. Markdown closes a block
only with a marker of the same character and at least the opening run's length, which is what lets
a four-backtick block carry a three-backtick line as text. Here that inner line closes the block,
and every line after it is read with the fence state inverted: the anchor scan stops seeing the
headings below it, or starts reading shell comments as headings; the log-sample gate reads a
documented line out of prose, or stops reading one inside a block; the commit hook exempts prose
from the wrap, or stops exempting a paste.

This tree already writes the shape the rule is missing. `docs/adr/ADR-0005-llamacpp-engine.md`
opens a four-backtick block for the reason markdown offers it: the grammar printed inside it spells
`"```json"`. That inner marker sits in the middle of its line, so nothing toggles, and it is one
reflow of that grammar away from sitting at the start of one. A commit message can nest the same
way, a four-backtick paste carrying a fence, though the history holds no fenced message at all.

**Why it was left.** The close that made the answer shared was about the spelling rather than the
reading, and it moved no gate's behaviour by design: the three copies it replaced all toggled on
the marker, so teaching the shared answer the closing rule would have been a behaviour change
landing in the same commit as a refactor and three suites would have had to be read for what it
moved.

**What would close it.** Either the closing rule in the shared answer, which means the toggle
carries the character and the run length that opened the block and a caller asks about a line
rather than about a marker, with each of the three suites holding its own behaviour under it; or a
written argument that a document nesting a block is rare enough and visible enough that the three
gates may read it wrongly, with the one four-backtick block in this tree named as the case that
stays safe by its own layout.

## Trail

- 2026-09-12: opened by the close of
  [R-445](445-three-gates-each-spell-the-markdown-fence-for-themselves.md), recorded at the
  [ADR-0026 one-home addendum](../../adr/ADR-0026-prose-style-gates.md), which states what the
  shared reading covers and what it leaves.
- 2026-09-14: still not fired, measured rather than argued. Every `.md` file `treewalk.walk_files`
  hands over was read line by line under markdown's own closing rule, opening on a marker and
  closing only on one of the same character and at least the opening run's length: no marker at
  the start of a line falls inside another block, in any document in this tree. The one case the
  entry names is where it was. `docs/adr/ADR-0005-llamacpp-engine.md` opens a four-backtick block
  at line 1630 and closes it at 1634, and the `"```json"` inside it sits at line 1631 with the
  marker in the middle of the line, so nothing toggles. It is still one reflow away from the start
  of a line. The two branches are unchanged.
- 2026-09-15: landed, the first branch taken. The search was run once more over every `.md` file
  `treewalk.walk_files` hands over, 764 of them, each read under markdown's own closing rule: no
  marker at the start of a line falls inside another block anywhere in this tree, and the
  four-backtick block in `docs/adr/ADR-0005-llamacpp-engine.md` still keeps its inner marker in
  the middle of line 1631. So the change moves no answer about anything committed here.

  It landed anyway, because the second branch cannot be written honestly. Two of the directions a
  wrong reading takes are quiet rather than visible: a shell comment inside a block read as a
  heading makes the anchor scan offer an anchor no renderer offers, so a broken pointer at it
  passes, and a sample inside a block the log-sample gate stops reading is a documented line
  nothing holds to its call site. The shared answer is now `Fences`, a reading of a document
  rather than a test on a line, and `is_fence` is gone. The three gates, the four suites and the
  mutation table are in the
  [ADR-0026 closing-rule addendum](../../adr/ADR-0026-prose-style-gates.md).
