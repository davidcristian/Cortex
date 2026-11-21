# The health probe's bound is on each read where a lease asks it

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Verified:** 2026-11-21

`LlamaServerProbe.fault` (`cortex_inference/serving_probe.py`) gives the transport its `timeout_s`
as one httpx number, which bounds each read of the answer and not the whole of it. The serving
watch puts a bound of its own around the call (`ServingWatch._ask`, `cortex_core/serving_watch.py`).
`MultiServerModelManager._claim` (`cortex_core/model.py`) does not: it awaits the probe of a
subagent's GPU server before each lease of it, with that server's slot counted as busy.

On 2026-11-21 a loopback server that sent the 57 bytes of its `/health` header one at a time was
waited on for 14.5 times the probe's `timeout_s`, and the probe then returned ready.

## Proposal

Put the probe's exchange under one bound, as `answered_within`
(`cortex_inference/probe_bound.py`) does for the system message, effort and trace budget probes,
and return `wording.down` when the bound ends the exchange. A test server that sends its header a
byte at a time, as `tests/drip_server.py` sends a body, is the test.

**What closes it.** The bound with its test, and the module doc stating it.

## History

- 2026-11-21: filed beside
  [R-1274](1274-the-effort-checks-props-read-has-no-measured-answer-time.md), whose probe has a
  bound on the whole answer.
