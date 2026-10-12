# A recalled tainted memory names its runs without the note

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)
**Trigger:** a deployment or a row that sets `CORTEX_MEMORY_ON_TAINTED=record`.
**Verified:** 2026-10-12

A recorded exchange names its turn's tool runs on a `Tools run` line (ADR-0074 decision 6), and
`_render_memory_context` (`cortex_core/turn_context.py`) puts `RECALLED_RUNS_NOTE`, which says a
run on that line ran in that earlier conversation only, at the start of the trusted section. A
tainted memory is fenced in its own section, under the header that says it is quoted data, and
that header has no note. When every hit is tainted, the block shows `Tools run: ...` lines with no
note at all, the shape that led a recalled reply to be claimed again with no call
([recalled-tool-runs.md](../../readings/recalled-tool-runs.md#results-over-the-stored-reminder)).

Tainted turns are recorded only with `CORTEX_MEMORY_ON_TAINTED=record`
([ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)); the default skips them, so the
default deployment stores no tainted row.

## What to do

Write rows and a pass rule first, over a store whose rows are tainted and name a run, then draw
the note in the fenced section's header (or as its own line above both sections) against the
current header. The fenced header is also framing for injected text
([ADR-0013](../../adr/ADR-0013-untrusted-content.md)), so the rows include an injection case.

## History

- 2026-10-12: filed when the trusted section's note shipped, since only that section was drawn.
