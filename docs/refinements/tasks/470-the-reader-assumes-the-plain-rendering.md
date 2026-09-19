# The reader assumes the plain rendering

**Status:** done 2026-09-12
**Area:** repo-checks
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

`scripts/trailwidth.py` cuts the field's rendering out with ` dropped=`, which is `PlainFormatter`'s
layout and only that one. Under `packed` the same record is one JSON object per line with the
fields under their own key, so every capture is a file the reader rejects with `no memory.recall
line carrying a dropped field`. The stack is fine, the trail is on, and the rendering is the one the
memory runbook recommends two paragraphs above the recipe. `just recall-width` recreates the brain
itself and sets neither variable, so a run through the recipe reads plain lines; the failure reaches
an operator who captures by hand, or a deployment that has set the packed rendering.

## History

- 2026-08-27: opened by the close of
  [R-454](454-the-readers-needles-are-not-tied-to-the-sink.md), which made the reader's search text
  answerable to the sink and left the layout it reads them in answerable to nothing.
- 2026-09-10: the trigger has not fired and the reader is unchanged. It still cuts the field out
  with a pattern anchored on ` dropped=` and still finds a record by `[A-Z]+:[^\s:]+:memory.recall`,
  which is `PlainFormatter`'s layout. The memory runbook still offers `CORTEX_LOG_FORMAT=packed` as
  the way to read a trail line without slicing it, and the local-dev runbook still names it for a
  deployment that collects lines.
- 2026-09-12: closed, by naming the assumption in the refusal rather than by reading the second
  rendering. `packed_trail` reads each line of a capture from its first `{`, so the prefix `docker
  compose logs` writes does not hide the object, and a line qualifies when it has the trail's
  message under the `message` key. When a capture has one, the refusal adds `; this capture holds
  one in the packed rendering, which this reader does not measure`; when it does not, the refusal
  keeps its old words. Measuring packed widths was declined rather than deferred: the width this
  reader reports is what `VALUE_CHARS` is argued against, that bound is applied in `render_value`,
  which only the plain rendering passes through
  ([R-336](336-packed-values-keep-their-whole-length.md)), and the same trail record at its shipped
  caps renders at 2,258 characters plain against 2,478 packed. Five mutations of the reading each
  fail one to three of the 33 tests in
  [test_trailwidth.py](../../../scripts/tests/test_trailwidth.py); the table is in
  [ADR-0051 decision 16](../../adr/ADR-0051-log-line-rendering.md). `scripts/trailwidth.py` now
  stands at 296 lines against the 300-line cap, so the next change to it is a split.
