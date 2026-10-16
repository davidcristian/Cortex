# A brain started before the cortex serves never sends a trace budget

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Verified:** 2026-10-16

With `CORTEX_INFERENCE_TRACE_LEVER=auto`, `resolve_send_trace_budget` asks the cortex's endpoint
once, at wiring, and `LlamaCppBackend` keeps the answer for the life of the process.
`reads_a_trace_budget` returns `False` on a transport error and on any status other than the 400
naming the key, so a probe that never reached a serving engine is read as an engine that does not
parse the key. Read from the code, that brain then never sends `reasoning_budget_tokens` and logs
`trace budget not sent because its setting is off` once, so a reasoning trace has no budget of its
own until the brain is restarted.

Compose orders the brain after a model host whose healthcheck needs the cortex `ready`, so `just
up` is safe. The case is any start in another order: the brain restarted while the model host is
stopped, restarting, or still loading (a 503 `Loading model`), which is what an operator's
`docker restart` of both does.

## Reproduction

On the shared stack: `docker stop` the model host, `docker restart` the brain, then `docker start`
the model host. The brain logs `trace budget probe failed` with `Name or service not known` and
serves, and once the cortex is `ready` it answers turns. A brain started while the cortex loads
gets the 503 and, by the code above, logs `trace budget probe answered reads_budget=False`.

## What to do

1. Make the probe's answer three-valued: reads, does not read, and no answer (a transport error or
   a 5xx).
2. On no answer, keep the setting unsettled and ask again before the next request, until an
   answer arrives; log the settled answer once.
3. Test both orders with a fake server that is down, then loading, then serving.
4. Rerun the reproduction above.

[R-648](648-nothing-asks-the-trace-setting-again-when-the-engine-moves.md) is the other half, an
answer that went stale because the engine changed.

## History

- 2026-10-16: filed by the startup flows (brain started while the model host was stopped).
