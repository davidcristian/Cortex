# The reader assumes the plain rendering

**Status:** landed 2026-09-12
**Area:** repo-gates
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-27 by the close of
[R-454](454-the-readers-needles-are-not-tied-to-the-sink.md), which held the two words
`scripts/trailwidth.py` looks for and left the shape it looks for them in unstated.

The reader cuts the field's rendering out with ` dropped=`, which is `PlainFormatter`'s layout and
only that one. Under `packed` the same record is one JSON object per line, the fields under their
own key, and every capture is a file the reader rejects with `no memory.recall line carrying a
dropped field`. That is the misattributed refusal the tied needles just removed, arriving by
another route: the stack is fine, the trail is on, and the rendering is the one the memory runbook
recommends two paragraphs above the recipe.

**Why it was left.** `just recall-width` recreates the brain itself and names neither variable, so
a run through the recipe takes the shipped default and reads plain lines. It bites the operator who
captures by hand, or a deployment that has set the packed rendering and left it set.

**What would close it.** Either the reader reads the second rendering, which is a JSON path rather
than a regular expression and is the smaller half, or the refusal names the assumption, saying that
a capture holding no plain trail line may be a packed one. The first is worth more if the whole
line's width is ever measured under both renderings, since the two layouts do not spend the same
number of characters on the same record.

**Landed 2026-09-12, as the second of those and not the first.** `packed_trail` reads each line of
a capture from its first `{`, so the prefix `docker compose logs` writes does not hide the object,
and a line qualifies by carrying the trail's message under the `message` key. When a capture holds
one, the refusal adds `; this capture holds one in the packed rendering, which this reader does not
measure`; when it does not, the refusal keeps the words the origin record and
[R-454](454-the-readers-needles-are-not-tied-to-the-sink.md) quote. The first option was declined
rather than deferred: the width this reader reports is what `VALUE_CHARS` is argued against, that
bound is spent in `render_value`, which only the plain rendering passes through
([R-336](336-packed-values-keep-their-whole-length.md)), and the same trail record at its shipped
caps renders at 2,258 characters plain against 2,478 packed, so a packed width measures a different
layout and no bound at all. Five mutations of the reading each fail one to three of the 33 tests in
[test_trailwidth.py](../../../scripts/tests/test_trailwidth.py); the table is in the
[ADR-0038 packed-capture addendum](../../adr/ADR-0038-ranked-recall.md#packed-capture-addendum-2026-09-12-the-reader-names-the-rendering-it-does-not-measure).

## Trail

- 2026-08-27: opened by the close of
  [R-454](454-the-readers-needles-are-not-tied-to-the-sink.md), which made the reader's words
  answerable to the sink and left the layout it reads them in answerable to nothing.
- 2026-09-10: the trigger has not fired and the reader is unchanged. `scripts/trailwidth.py` still
  cuts the field out with a pattern anchored on ` dropped=` and still finds a record by
  `[A-Z]+:[^\s:]+:memory.recall`, which is `PlainFormatter`'s layout, so a packed capture is
  rejected rather than measured. The memory runbook still offers `CORTEX_LOG_FORMAT=packed` as the
  way to read a trail line without slicing it, and the local-dev runbook still names it for a
  deployment that collects lines, so the two documents still point in different directions.
- 2026-09-12: landed. The refusal names the packed rendering when the capture holds a trail line in
  it, and reading that rendering's widths was declined for the reason above rather than left open.
  Nothing was opened by the close: what a packed line costs is [R-336](336-packed-values-keep-their-whole-length.md)'s
  subject and was measured there the same day. `scripts/trailwidth.py` now stands at 296 lines
  against the 300-line cap, so the next change to it is a split.
