# A fence marker opening a line inside another block toggles every reader

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-12
**Trigger:** a document in this tree writes a fence marker at the start of a line inside another
fenced block, which one search over the markdown answers.

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
