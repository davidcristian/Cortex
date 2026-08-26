# The reader assumes the plain rendering

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a capture taken from a deployment running `CORTEX_LOG_FORMAT=packed`, which the same
runbook paragraph offers as the way to read a trail line without slicing it
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-27 by the close of
[R-454](454-the-readers-needles-are-not-tied-to-the-sink.md), which held the two words
`scripts/trailwidth.py` looks for and left the shape it looks for them in unstated.

The reader cuts the field's rendering out with ` dropped=`, which is `PlainFormatter`'s layout and
only that one. Under `packed` the same record is one JSON object per line, the fields under their
own key, and every capture is a file the reader refuses with `no memory.recall line carrying a
dropped field`. That is the misattributed refusal the tied needles just removed, arriving through
the other door: the stack is fine, the trail is on, and the rendering is the one the memory runbook
recommends two paragraphs above the recipe.

**Why it was left.** `just recall-width` recreates the brain itself and names neither variable, so
a run through the recipe takes the shipped default and reads plain lines. It bites the operator who
captures by hand, or a deployment that has set the packed rendering and left it set.

**What would close it.** Either the reader learns the second rendering, which is a JSON path rather
than a regular expression and is the smaller half, or the refusal names the assumption, saying that
a capture holding no plain trail line may be a packed one. The first is worth more if the whole
line's width is ever measured under both renderings, since the two layouts do not spend the same
number of characters on the same record.

## Trail

- 2026-08-27: opened by the close of
  [R-454](454-the-readers-needles-are-not-tied-to-the-sink.md), which made the reader's words
  answerable to the sink and left the layout it reads them in answerable to nothing.
