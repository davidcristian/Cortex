# The evict list accepts the deep tier it makes room for

**Status:** open, actionable
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-17

`CORTEX_SWAP_EVICT_MODELS` names the hosted tiers a handoff stops before the deep model loads, and
nothing checks that it leaves out the deep model itself. `SwapConfig.evict_models` is a bare
`tuple[str, ...]` (`config_swap.py:115`), and `ResidencyPlan.__post_init__` (`model_host.py`)
checks every numeric bound on the plan and never compares `evict_models` with `brain_model` or
`cortex_model`. An evict list of `cortex`, `brain`, `subagent-gpu` and `nosuch` loads without
error.

Every reader of the list treats a listed id as a standing peer to keep running, so listing the deep
tier keeps the deep model running outside a handoff. Both of the following were run under
`brain/.venv/bin/python` against `ScriptedModelHost`, with the cortex running and the plan's evict
list set to `("brain",)`:

- One `sweep_tiers` pass with the fence open, which is every pass outside a handoff, called
  `status` and then `start` on `brain`, and left `brain` and `cortex` both running.
- `converge_residency` at boot made one non-status call, `start` on `brain`, returned `True`, and
  left both running. Its own docstring says "the deep model is not a peer", and nothing enforces
  that.

The swap back does the same through `restart_evicted`, which `restore_standing` calls after it
stops the deep model. That path was read and not run. On the card this repo is developed on, the
deep pick's measured VRAM cost is 19125 MiB (a comment in `docker/docker-compose.gpu.yml`), and
`swap_in`'s docstring records that no measured pairing of the cortex with a deep candidate fits
24 GB. So the likely outcome is an overcommitted card, which `config_swap.py`'s co-residency error
message says halves the deep model's decode rate. That outcome is inferred from those records and
was not measured here.

**What to build.** `ResidencyPlan.__post_init__` raises when `evict_models` contains `brain_model`,
naming both `CORTEX_SWAP_EVICT_MODELS` and `CORTEX_MODEL_BRAIN` in the message. The plan is the one
object that holds all three ids, and `build_swap_scope` constructs it at boot, so the error stops
the boot before any handoff runs. The check raises from a frozen dataclass, not from a pydantic
validator, so the message carries only the ids and none of the endpoints `SwapConfig` holds. A
core test adds the refused plan, and the paragraph of `docs/runbooks/model-swap.md` that lists
what the brain refuses to boot with gains one sentence. Whether to refuse the cortex id as well is
for the builder to decide: listing it turns the sweep into something that restarts a stopped
cortex, which is the start the pass-that-starts-the-cortex entry
([R-310](310-a-pass-that-starts-the-cortex.md)) has not built, and that case was not run here.

It waits on nothing in the tree. It was not built on 2026-09-17 only because a GPU sitting was
re-importing `brain/packages/core/` at the time.

## Trail

- 2026-09-17: filed by the trigger sweep of the placer-width entry
  ([R-200](200-placer-one-bit-per-card.md)), which found the model host can carry only three tiers,
  so a deployment listing more than the subagent tier can only be listing the cortex, the deep tier
  or an id no roster has, and ran the deep-tier case against the scripted host.
