# A question sent while the model host restarts an exited cortex fails at once

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Verified:** 2026-10-16

A turn waits for a cortex that is still loading only on llama-server's 503 `Loading model`
(ADR-0054 decision 10). Before the restarted llama-server listens, a request fails in transport
with `llama-server request failed for model 'cortex'`, and the turn ends at once, even when the
model host's supervisor (decision 9) is already starting an exited cortex again and
`GET /models/cortex` reads `loading`. In the model host restart flow of the
[startup readings](../../readings/startup-order-and-settings.md) that window was the first 0.11 of
the restart-to-ready time; the window after a supervisor restart of an exited child is not
measured.

## What to do

1. Measure the window: end the cortex child inside the model host container and poll
   `GET :8080/health` and `GET :9300/models/cortex` every half second until `ready`.
2. Decide what the brain reads to tell a restart in progress from a server that is down: the
   model host's state through the `ModelHost` port exists only with escalation on, so a deployment
   without it needs another answer, or the case is accepted there.
3. Wait as for a 503 only while the restart is in progress, and test with fakes a server that is
   down and not restarting (fails at once) and one the host reports `loading` (waits).

## History

- 2026-10-16: filed when the load wait was built, which leaves this case failing at once.
