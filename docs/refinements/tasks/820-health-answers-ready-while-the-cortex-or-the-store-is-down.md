# Health answers ready while the cortex or the store is down

**Status:** open, actionable
**Area:** rpc-transport
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Verified:** 2026-10-10

The overlay's connection dot is the person's view of whether a turn can work, and it reads
`BrainService.Health`. `Health` reads only the residency report
([server.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/server.py)), and with
escalation off, the shipped default, the brain holds no residency, so `Health` answers
`ready=True` whatever the cortex and the store are doing. ADR-0054 says this in its context, so the
code matches its record; the record does not say what the dot should show in the two states below.

On the Linux shell on 2026-10-10
([readings](../../readings/store-and-process-restarts.md)):

- With the cortex's `llama-server` killed inside the model host container, the model host
  answered `failed` for the cortex, every question ended in
  `inference_failed: llama-server request failed for model 'cortex'`, and the dot stayed green
  until an operator started the cortex again.
- With Redis stopped, a question's reply could not be stored and the turn ended in
  `session_store_unavailable`, and the dot stayed green. With escalation on, `Health` reads the
  residency report and still does not read the store, so that half holds there too.

**Reproduction.** Bring up `docker/docker-compose.yml` with `docker/docker-compose.gpu.yml`, then
`docker exec <model-host> kill -9 <llama-server pid>` or `docker stop <redis>`, and call `Health`.

**What deciding it needs.** A choice of what `Health` reads and how often: a store ping and the
model host's `GET /models/cortex` per call, or a background reading `Health` returns, as the
residency report already is. The second keeps `Health` cheap under the body's probe rate. The note
text for each state is a wording choice the overlay shows as the dot's line.

## History

- 2026-10-10: filed from the store and process restart flows run on the Linux shell.
