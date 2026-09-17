# The compose brain cannot receive most of its own settings

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)
**Verified:** 2026-09-17

`CORTEX_OUTPUT_GUARDRAIL` is read by `BrainRuntimeConfig` and named in no compose file, so an
operator who exports it before `just up` gets a brain running the default `redact` policy and no
error. The same is true of most settings the brain reads. Measured on 2026-09-17 by setting every
field of six settings classes to a probe value and rendering `docker compose config` for the base
file alone and for the base file with each overlay in turn (the loopback overlay needs the gpu one
and was skipped), then looking for the probe value in the output:

| Settings class | Fields | Passed through | Set by a file | Named nowhere |
|---|---|---|---|---|
| `BrainRuntimeConfig` | 9 | 1 | 1 | 7 |
| `SwapConfig` | 13 | 1 | 1 | 11 |
| `SeamServerConfig` | 5 | 1 | 1 | 3 |
| `ReplyBoundsConfig` | 3 | 0 | 0 | 3 |
| `InferenceConfig` | 5 | 1 | 2 | 2 |
| `BodyConfig` and `LoggingConfig` | 7 | 6 | 1 | 0 |

The 26 named nowhere include `CORTEX_OUTPUT_GUARDRAIL`, `CORTEX_GENERATE_TITLES`, the three
`CORTEX_HISTORY_` settings, `CORTEX_REPLY_MAX_TOKENS`, `CORTEX_REPLY_THINKING` and
`CORTEX_INFERENCE_STALL_TIMEOUT_S`. Two of them are deliberate: `CORTEX_SEAM_PORT` is tied to the
port the base file publishes, and `docker-compose.gpu.yml` tells an operator to add the swap
settings to the brain environment by editing it. The rest have no route at all. `ToolsConfig`,
`SubagentsConfig` and the sidecars' own settings were not measured.

The memory overlay already solved this for `MemoryConfig`: it passes every field it does not set
through by name, so a value set on the host reaches the brain and an unset one never enters the
container, and each default stays declared once in Python.

**What would be built.** The same rule in `docker/docker-compose.yml` for the brain service, over
every field of the classes above except `CORTEX_SEAM_PORT` and the ones the file sets, with the
swap settings moved from edit-the-file to pass-through so `docker-compose.gpu.yml` can drop that
instruction. Then a gate that holds the list to the settings classes, since a field added in Python
is otherwise missed again: `defaultcheck.py` and `bindcheck.py` already read the compose files, and
the field names would have to be read out of the settings modules without importing them, the way
`moduleconstants.py` reads a module's top level. The first half is a compose-only change; the gate
is the larger half and could land separately.

## Trail

- 2026-09-17: filed by the trigger sweep over
  [R-284](284-the-lookalike-policy-as-the-shipped-default.md), which found that the policy it asks
  about cannot be switched on in the compose stack. Recorded in the ADR-0015 addendum of
  2026-09-17.
