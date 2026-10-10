# The model host's healthcheck warns about a deep tier the roster lacks

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0053](../../adr/ADR-0053-model-host-supervisor.md)
**Verified:** 2026-10-10

The `model-host` healthcheck in
[docker-compose.gpu.yml](../../../docker/docker-compose.gpu.yml) asks `GET /models/cortex` and,
when that is not `ready`, `GET /models/brain`. With escalation off the roster has no deep tier, so
every check made while the cortex loads ends in a 404, and the sidecar logs `a model-host request
failed` at `WARNING` with `unknown model 'brain'; this host serves cortex`. That is every 2 s for
the first 180 s of a container's life and every 30 s after, during each cortex load, including the
restart after an unasked exit. An operator reads it as a misconfigured deep tier.

**Reproduction.** Bring up the GPU stack with escalation off, `kill -9` the cortex's
`llama-server` inside the model host, and read `docker logs` for the model host during the reload.

**What deciding it needs.** Either the healthcheck asks for the deep tier only when it is in the
roster (it can read `models` from `GET /health`), or a 404 for a model a check asks about is logged
below `WARNING`. The second hides a real misconfiguration from the brain's own calls, which use the
same route.

## History

- 2026-10-10: filed while closing [310](310-a-pass-that-starts-the-cortex.md), whose live run showed
  these warnings during the restarted cortex's load.
