# The compose brain cannot receive most of its own settings

**Status:** landed 2026-09-17
**Area:** cross-cutting
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

`CORTEX_OUTPUT_GUARDRAIL` is read by `BrainRuntimeConfig` and named in no compose file, so an
operator who exports it before `just up` gets a brain running the default `redact` policy and no
error. The same is true of most settings the brain reads. Measured on 2026-09-17 by setting every
field of the eleven settings classes in the orchestrator package to a distinct probe value and
rendering `docker compose config` for the base file alone, for the base file with each overlay in
turn, for the gpu and loopback pair, and for every overlay at once, then reading the **brain
service's** environment. A second render with every probe unset separates a bare pass-through from
one carrying a compose default. The email overlay renders only with its required credentials set,
and the loopback overlay touches only `model-host`.

| Settings class | Fields | Passed through | Set by a file | Named nowhere |
|---|---|---|---|---|
| `SeamServerConfig` | 5 | 1 | 1 | 3 |
| `BrainRuntimeConfig` | 9 | 0 | 1 | 8 |
| `InferenceConfig` | 5 | 1 | 2 | 2 |
| `MemoryConfig` | 13 | 10 | 3 | 0 |
| `SwapConfig` | 13 | 0 | 1 | 12 |
| `ReplyBoundsConfig` | 3 | 0 | 0 | 3 |
| `BodyConfig` | 6 | 5 | 1 | 0 |
| `LoggingConfig` | 1 | 1 | 0 | 0 |
| `ToolsConfig` | 12 | 3 | 3 | 6 |
| `SubagentsConfig` | 16 | 6 | 3 | 7 |
| `ScheduleConfig` | 6 | 2 | 0 | 4 |

A search of the whole rendered output, which the first reading used, counts `CORTEX_MODEL_CORTEX`
and `CORTEX_MODEL_BRAIN` as passed through, because the gpu overlay hands both to the `model-host`
sidecar. The brain never received them, so a host renaming a tier renamed it on the sidecar alone.
`docker-compose.gpu.yml` also told an operator to turn escalation on by editing the brain's
environment in that file, since a `.env` entry could not reach it.

The memory overlay already solved this for `MemoryConfig`: it passes every field it does not set
through by name, so a value set on the host reaches the brain and an unset one never enters the
container, and each default stays declared once in Python.

## The census after the change, one verdict per field

Rendered the same way once the pass-through landed. Every field now reaches the brain in the
stacks whose capability reads it, except the two marked as deliberately unnamed.

- **Passed bare by the base file:** `CORTEX_SEAM_CONVERSE_BUFFER`, `CORTEX_SEAM_CONFIRM_TIMEOUT_S`,
  `CORTEX_VRAM_SOFT_CAP_GB`, `CORTEX_VRAM_CORTEX_GB`, `CORTEX_HISTORY_CHAR_BUDGET`,
  `CORTEX_HISTORY_SUMMARY`, `CORTEX_HISTORY_RECAP_MIN_CHARS`, `CORTEX_OUTPUT_GUARDRAIL`,
  `CORTEX_GENERATE_TITLES`, `CORTEX_REPLY_MAX_TOKENS`, `CORTEX_REPLY_THINKING`,
  `CORTEX_REPLY_TRACE_TOKENS`, `CORTEX_TOOLS_ON_UNAVAILABLE`, `CORTEX_TOOLS_GATED`,
  `CORTEX_TOOLS_GATE_REASONS` and `CORTEX_TOOLS_COSTS` (the whole map as JSON; per-key entries still
  merge over it, checked against `ToolsConfig`), `CORTEX_TOOLS_AUDIT_FILE`,
  `CORTEX_SCHEDULE_POLL_S`, `CORTEX_SCHEDULE_LEASE_S`, `CORTEX_SCHEDULE_CLAIM_LIMIT`,
  `CORTEX_SCHEDULE_MAX_ACTIVE`.
- **Passed with a compose default by the base file:** `CORTEX_SEAM_TOKEN`, `CORTEX_LOG_FORMAT`,
  `CORTEX_TOOLS_SALIENCE`, `CORTEX_TOOLS_SALIENCE_LIMIT`, `CORTEX_TOOLS_CALL_TIMEOUT_S`,
  `CORTEX_SCHEDULE_BACKEND`, `CORTEX_SCHEDULE_TZ`.
- **Set by the base file (topology):** `CORTEX_SEAM_HOST`, `CORTEX_REDIS_URL`.
- **Passed bare by the gpu overlay:** `CORTEX_INFERENCE_TRACE_LEVER`,
  `CORTEX_INFERENCE_STALL_TIMEOUT_S`, `CORTEX_MODEL_CORTEX`, `CORTEX_MODEL_BRAIN`,
  `CORTEX_ESCALATION`, `CORTEX_MODELHOST_BACKEND`, `CORTEX_MODELHOST_TIMEOUT_S`,
  `CORTEX_SWAP_EVICT_MODELS`, `CORTEX_SWAP_CORESIDENT`, `CORTEX_SWAP_BRAIN_VRAM_MIB`,
  `CORTEX_SWAP_BRAIN_DECODE_TPS`, `CORTEX_SWAP_DRAIN_TIMEOUT_S`, `CORTEX_SWAP_LOAD_TIMEOUT_S`,
  `CORTEX_SWAP_TIER_HEAL_S`.
- **Set by the gpu overlay (topology):** `CORTEX_INFERENCE_BACKEND`, `CORTEX_INFERENCE_ENDPOINT`,
  `CORTEX_MODELHOST_ENDPOINT`, and now `CORTEX_BRAIN_ENDPOINT`, which only a brain with escalation
  on reads.
- **Memory overlay:** the backend, DSN and embedder endpoint set; the other ten passed bare.
- **Body overlay:** `CORTEX_BODY_BACKEND` set; `CORTEX_BODY_ENDPOINT`, the four capture and call
  bounds and `CORTEX_VISION` passed with compose defaults. `CORTEX_VISION` is read only with a body,
  so it belongs there.
- **Subagents overlay:** `CORTEX_SUBAGENTS_BACKEND` and `CORTEX_SUBAGENTS_ENDPOINT` set;
  `CORTEX_SUBAGENTS_GPU_ENDPOINT` and the five resource figures passed with compose defaults;
  `CORTEX_SUBAGENTS_MODEL`, `CORTEX_SUBAGENTS_MODEL_DESCRIPTION`,
  `CORTEX_SUBAGENTS_STALL_TIMEOUT_S`, `CORTEX_SUBAGENTS_ADMISSION_WAIT_S`,
  `CORTEX_SUBAGENTS_MAX_TOKENS`, `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` and
  `CORTEX_SUBAGENTS_CONSTRAIN_OUTPUT` passed bare.
- **Map settings contributed one key at a time by the overlay that brings the server:**
  `CORTEX_TOOLS_BACKEND` and `CORTEX_TOOLS_ENDPOINTS__<name>` (tools and email overlays),
  `CORTEX_TOOLS_ALLOW__FILESYSTEM` (tools overlay), `CORTEX_SUBAGENTS_ROSTER__<name>`
  (subagents-roster overlay).
- **Deliberately named by no file:** `CORTEX_SEAM_PORT`, fixed at 50051 by the base file's publish
  and healthcheck, and `CORTEX_TOOLS_ENDPOINT`, the single-sidecar form the brain refuses beside
  the per-sidecar keys the tool overlays set.

The sidecars' own settings classes (`ModelHostConfig`, `EmailConfig`, `SmtpConfig`) were not part
of this census, being read by other containers.

## Trail

- 2026-09-17: filed by the trigger sweep over
  [R-284](284-the-lookalike-policy-as-the-shipped-default.md), which found that the policy it asks
  about cannot be switched on in the compose stack. Recorded in the ADR-0015 addendum of
  2026-09-17.
- 2026-09-17: landed as the pass-through above, in `docker/docker-compose.yml`,
  `docker/docker-compose.gpu.yml` and `docker/docker-compose.subagents.yml`, with the gpu overlay's
  edit-this-file instruction for escalation replaced by host settings. A bare key resolves from
  the host shell and from `.env`, and an unset one is absent from the container, both checked with
  a throwaway service. The gate that holds the list to the settings classes was not built in the
  same change and is [R-687](687-nothing-holds-the-compose-brain-to-its-settings-classes.md).
  The triggers of [R-023](023-converse-reconnect-first-event.md),
  [R-024](024-disconnect-mid-handoff-teardown.md), [R-199](199-sweep-start-not-serialized.md) and
  [R-279](279-confirm-card-offers-an-impossible-handoff.md) read a comment-only mention of
  `CORTEX_ESCALATION` as "no stack can escalate", which the bare key broke, so they now look for a
  key carrying a value. Recorded in the ADR-0015 addendum of 2026-09-17 on the composed brain.
