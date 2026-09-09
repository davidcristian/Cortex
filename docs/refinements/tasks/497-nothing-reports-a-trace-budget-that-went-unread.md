# Nothing reports a trace budget the engine never read

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-09
**Trigger:** a deployment that set `CORTEX_REPLY_TRACE_TOKENS` to a count and cannot tell whether it
did anything, or a side call that returns an empty reply on an endpoint whose boot probe answered
that the engine reads no per-request trace budget.

Opened 2026-08-29 by the close of
[R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which gave the port a count the
engine may or may not read and left the reporting where the switch's already was.

`drain_text` warns when a request that asked for no thinking is answered with a trace anyway, which
is the one runtime line saying a lever did not hold. It fires on `bounds.thinking` and does not read
`bounds.trace_tokens`, so nothing reports the three cases the new count adds: a bound naming a
count on a deployment whose lever is off, a bound naming a count the engine took and ignored, and a
positive count that was honoured at a different number than the one asked for. The middle case
cannot happen on a probed deployment, which is the point of the probe, and the first is a
configuration a person chose.

**Why it was left.** The count's producers are exactly the ones the existing line already covers:
all three side calls send the switch too, so a trace arriving against a zero already prints, and it
prints for the right reason. What is genuinely unreported is a **positive** count that did nothing,
and there is no producer of one in the tree yet: `CORTEX_REPLY_TRACE_TOKENS` ships unset, and a
deployment that sets it is watching the thinking status the count bounds, which is the most direct
report there is.

**What would close it.** The cheap half is one condition: report when a bound named a count and the
trace came back longer than it, which needs `drain_text` to count characters it already counts and
a rate to compare them at, so it is really a question of what a token is worth in characters and
whether a line that guesses is worth more than no line. The honest half is to say it where the
count is decided instead: the composition root knows both the lever and the deployment's own
`CORTEX_REPLY_TRACE_TOKENS`, so a deployment that named a count on an engine that reads none could
be told at boot, once, rather than never. That one is a few lines and no guessing, and it is
probably the whole of what this needs.

## Trail

- 2026-08-29: opened by the close of
  [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which added a per-request
  count whose failure to be read goes as unreported as the switch's did before the drain's warning.
- 2026-09-07: neither limb of the trigger has fired, and the premise was re-derived and holds.
  `CORTEX_REPLY_TRACE_TOKENS` is set by nothing in this tree: it is named in `config_reply.py`, the
  GPU runbook's settings table, the orchestrator module doc, the origin ADR and these backlog
  files, and by no compose file, no justfile recipe and no workflow, and there is no `.env` at the
  repo root, so the field sits at its unset sentinel wherever the stack runs. The second limb was
  too vague to have a truth value and is narrowed above to the reading that would show it. What it
  now names cannot arise on this host either: the three side calls all send `thinking=False` and
  `trace_tokens=0`, `CORTEX_INFERENCE_TRACE_LEVER` defaults to `auto`, and both builds this machine
  can start answer the lever question `400` naming the field, so the zero reaches the engine on
  every tier this stack starts. `drain_text` is unchanged, reading `bounds.thinking` alone and
  never `bounds.trace_tokens`, so the three cases the count adds are still unreported.
