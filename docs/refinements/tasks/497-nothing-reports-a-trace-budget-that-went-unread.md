# Nothing reports a trace budget the engine never read

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** a deployment that set `CORTEX_REPLY_TRACE_TOKENS` to a count and cannot tell whether it
did anything, or a side call whose cap keeps emptying its reply on a tier nobody has probed.

Opened 2026-08-29 by the close of
[R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which gave the port a count the
engine may or may not read and left the reporting where the switch's already was.

`drain_text` warns when a request that asked for no thinking is answered with a trace anyway, which
is the one runtime line saying a lever did not hold. It fires on `bounds.thinking` and knows nothing
about `bounds.trace_tokens`, so the three cases the new count adds are all silent: a bound naming a
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
  count whose failure to be read is as silent as the switch's was before the drain's warning.
