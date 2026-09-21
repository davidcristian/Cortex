# Nothing reports a trace budget the engine never read

**Status:** done 2026-09-19
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

`drain_text` warns when a request that asked for no thinking is answered with a trace anyway, which
is the one runtime line saying a setting did not take effect. It reads `bounds.thinking` and never
`bounds.trace_tokens`, so nothing reports the three cases the count adds: a bound naming a count on
a deployment whose probe answered no, a bound naming a count the engine took and ignored, and a
positive count honoured at a different number than the one asked for. The middle case cannot happen
on a probed deployment, and the first is a configuration a person chose.

The count's producers on a shipped path are the ones the existing line already covers: all three
side calls send the switch too. What is genuinely unreported is a positive count that did nothing.
`CORTEX_REPLY_TRACE_TOKENS` ships unset, and the one producer of a positive count, which has
existed since 2026-09-11, is a measurement: `CORTEX_ENVELOPE_TRACE_TOKENS` in
`test_envelope_cost_live.py`, which answers the question for itself by asking
`reads_a_trace_budget` first and then asserting that the wire had the count.

## History

- 2026-08-29: opened by the close of
  [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md), which added a per-request
  count whose failure to be read goes as unreported as the switch's did before the drain's warning.
- 2026-09-07: neither clause of the trigger has fired, and the premise holds.
  `CORTEX_REPLY_TRACE_TOKENS` is set by nothing in this tree: it is named in `config_reply.py`, the
  GPU runbook's settings table, the orchestrator module doc, the origin ADR and these backlog files,
  and by no compose file, recipe or workflow, and there is no `.env` at the repo root. The second
  clause was too vague to have a truth value and is narrowed above. `drain_text` is unchanged.
- 2026-09-12: neither clause has fired, and the entry was wrong about two things. A producer of a
  positive count now exists, `CORTEX_ENVELOPE_TRACE_TOKENS` in the envelope harness, and the way it
  satisfies itself is the shape the close wants: ask the probe first, then read the key back off the
  wire. And the boot report is not a few lines, because the composition root does not hold the
  probe's answer; `resolve_trace_lever` is called inside `build_inference_backend` and its answer
  reaches only `LlamaCppBackend`. Nothing else moved.
- 2026-09-14: neither clause has fired and every claim held when checked again. One relation is
  worth recording: the entry beside this one about asking the probe again when the engine moves
  shares that obstacle and not the defect. A boot line reports an answer once; it does not repeat a
  stale one, so neither closes the other.
- 2026-09-19: neither clause has fired, and the entry was wrong that the probe's answer is visible
  nowhere. `reads_a_trace_budget` in `cortex_inference/trace_probe.py` logs `trace lever probe
  answered` with the endpoint and `lever` at `INFO`, and the GPU runbook has quoted that line since
  2026-08-29; what no line says is that a configured count will be dropped, so the defect stands at
  that narrower width. Since 2026-09-17 `docker/docker-compose.yml` passes
  `CORTEX_REPLY_TRACE_TOKENS` through by name with no value, so a count set on the host reaches the
  composed brain where before it could not. Nothing in the tree gives it a value, and there is still
  no `.env` at the repo root. `drain_text` still reads `bounds.thinking` alone, at `drain.py` line
  85.
- 2026-09-19: closed in the adapter, which already holds the probe's answer and each request's
  bounds. `LlamaCppBackend` logs one `WARNING`, `trace budget not sent because the trace lever is
  off`, with `model` and `trace_budget`, the first time a request on a backend built with the probe
  answered no names a count it will not send. The entry was too narrow to call only a positive count
  unreported: `CORTEX_REPLY_TRACE_TOKENS` accepts a zero, and a reply sending it with its switch on
  has nothing else asking for no trace, so that zero is reported too. A zero beside
  `thinking=False`, the side calls' shape, is not, since the drain already warns for it. The two
  cases that need a characters-per-token rate are declined in ADR-0049, and the GPU runbook quotes
  the line.
