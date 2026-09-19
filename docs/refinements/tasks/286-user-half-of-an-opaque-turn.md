# The user's half of an opaque turn

**Status:** open, waiting for its trigger
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-17
**Trigger:** a report, written on this entry's history or as a host task, of a sentence a user
asked the assistant to remember during an opaque turn and could not recall later. The loss needs
two settings together: memory recorded at all (`CORTEX_MEMORY_BACKEND=pgvector`, which the memory
overlay sets), and a turn that can go opaque, meaning `capture_screen` registered
(`CORTEX_BODY_BACKEND=grpc` with `CORTEX_VISION` at `on` or its `auto` default) or an MCP tool that
returns an image block. `CORTEX_MEMORY_ON_TAINTED` does not change it, because the opaque return
comes before that setting is read.

Opened 2026-08-16 by the per-source memory rules decline
([R-260](260-per-source-memory-rules.md)), which found that the loss that entry was written around
needs no source identifier at all. `record_exchange` returns before the write on `taint.opaque`,
and the text it would have written is `render_exchange`'s `User: <message>\nAssistant: <reply>`
([turn_output.py](../../../brain/packages/core/src/cortex_core/turn_output.py)), so a capture turn
drops the user's own sentence along with the transcription the drop exists for. The drop exists
because the assistant half of a capture turn is the untrusted payload in the one form that
survives; the user's half is text the user typed and an attacker cannot write. Recording only that
half preserves "remember that my invoice number is 4021" while persisting no pixel-derived prose at
all.

What makes it a decision rather than a two-line change is what a bare half means on recall. Most
capture turns open with a question, and `User: what does this say?` stored alone is noise a later
recall would rank against real memories, so this needs either a judgement of what is worth storing
at record time ([R-093](093-write-salience-policy.md)) or a rule narrow enough to state without
one. It also needs the origin's permission rewritten rather than assumed: the opaque drop is an
explicit decision in the vision record and in the tainted-recording record beside it, so a change
here rewrites the decision at both.

## History

- 2026-09-17: Checked, not triggered, and the trigger restated, because a user noticing a loss is
  not something the tree can be read for. The description holds: `record_exchange` in
  `turn_output.py` returns on `taint.opaque` before it reads `record_tainted_memory`, and
  `render_exchange` still writes `User: <message>\nAssistant: <reply>`; neither function has
  changed since 2026-08-31. One correction: an opaque turn is wider than a capture turn.
  `TaintLedger` in `untrusted.py` sets `opaque` on any untrusted result containing an image, and
  the MCP registry passes image blocks through (`result_images` in `cortex_tools/blocks.py`), so an
  image returned by an MCP tool drops the user's sentence the same way.
