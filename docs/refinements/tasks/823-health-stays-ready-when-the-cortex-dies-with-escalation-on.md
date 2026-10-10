# Health stays ready when the cortex dies with escalation on

**Status:** open, actionable
**Area:** rpc-transport
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Verified:** 2026-10-10

With escalation off, `Health` reads a `ServingWatch` that asks the cortex's own `GET /health` every
2 s, and the dot turns amber while the cortex is down (ADR-0054 decision 8,
[readings](../../readings/store-and-process-restarts.md#health-and-the-dot)). With escalation on,
`build_serving_watch` leaves the cortex out
([serving_builders.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/serving_builders.py)),
because a reading taken while a swap had the cortex stopped would outlive the swap by up to an
interval and show amber after a deep reply. The residency report does not cover the gap: the pass
reads the cortex only in `regain_residency`, which returns at once while the report is serving
([residency_regain.py](../../../brain/packages/core/src/cortex_core/residency_regain.py)). So a
cortex killed between handoffs leaves `Health` ready and the dot green while every turn ends in
`inference_failed`. This is read from the code; it has not been run.

**Reproduction.** Bring up the stack with `CORTEX_ESCALATION=true` and the supervisor model host,
`docker exec <model-host> kill -9 <cortex llama-server pid>`, then call `Health`.

**What deciding it needs.** Either the watch asks the cortex with escalation on too and drops a
reading taken while a handoff held the card (the manager's fence is synchronous, so the watch can
ask it before and after each pass), or the residency pass reads the cortex while serving and
publishes a report that is not serving. The second changes the report's writers, which decision 1
keeps to the manager.

## History

- 2026-10-10: filed when `Health` started reading the cortex's server with escalation off.
