# Nothing starts a stopped cortex outside boot, and no operator command exists

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Verified:** 2026-09-19
**Trigger:** a cortex that stops while the brain and the model host both keep running, which is the
one state neither boot path covers, or a second visit to the runbook's step 2. Both are operator
events, so the cheap recheck is whether the code has moved:
`brain/packages/core/src/cortex_core/residency_regain.py` still calls `host.status` twice and
`host.start` never, `proto/body.proto` still declares 16 RPCs across its two services with none of
them an operator command, and the model host's control API still offers the four routes it shipped
with (`/health`, `GET /models/{model}`, and start and stop, in
`brain/packages/model_manager/src/cortex_model_manager/api.py`).

The background pass
([residency_regain.py](../../../brain/packages/core/src/cortex_core/residency_regain.py)) detects a
cortex that is serving again and republishes residency, so the runbook's residency recovery is its
step 2 alone, one `POST /models/cortex/start` through the sidecar's control API. The pass will not
issue that start itself, so a machine whose cortex is genuinely down stays down until somebody asks
for it.

Two costs kept the start out of the pass. A cortex start is a whole tier load, minutes at tier
scale, and it is only worth anything if the pass then waits for readiness; `TierRechecker.aclose`
waits out the in-flight pass, so a waiting pass would hold shutdown for
`CORTEX_SWAP_LOAD_TIMEOUT_S`. Starting without waiting is cheap but records nothing, since the next
pass observes the result anyway. And the state this would act on is one where a start has already
failed twice inside the swap back, which makes the real question a retry budget rather than a
reading.

The alternative needs no concurrency argument: an operator-facing reconverge command, which is an
explicit request rather than a policy, and could therefore stop the deep tier, start the cortex and
wait for it. Its cost is a new interface. Nothing in
[proto/body.proto](../../../proto/body.proto) is an operator command, so it would be a decision
about that contract, and the alternative is that the operator uses the sidecar's control API
directly.

Two other places start the cortex with nobody asking, and both happen at boot. The sidecar's own
lifespan starts `boot_model` when the daemon comes up
([api.py](../../../brain/packages/model_manager/src/cortex_model_manager/api.py)), and the brain's
boot recovery starts the cortex and waits for it
([swap_recovery.py](../../../brain/packages/core/src/cortex_core/swap_recovery.py)). Restarting
either container brings a down cortex back.

With N peers in `CORTEX_SWAP_EVICT_MODELS` a pass makes at most 2N + 2 control calls, one `status`
and one `start` per peer plus the regain's two readings, and `TierRechecker.aclose`'s docstring has
said so since 2026-09-19. Until then it said two, which holds only while the variable is unset, the
shipped default (`config_swap.py` gives `evict_models` the empty tuple). On a deployment that sets
the variable, the shutdown wait a readiness-waiting start would lengthen is already longer than two
calls. The bound itself is unaffected, every call being cut off by the model host client's own
deadline.

## History

- 2026-08-18: Opened by the close of [116](116-reconciliation-without-a-turn.md), which argued that
  a background pass may read the machine freely and may write to the card only under a fence, so
  the reading was added and the start was not.
- 2026-09-08: Trigger checked and not fired, and the clause narrowed to code a reader can count
  rather than events nobody records. `regain_residency` makes two `status` calls and no `start`;
  `proto/body.proto` declares 16 RPCs, none an operator command; the control API declares four
  routes; and `evict_models` defaults to the empty tuple, which is what makes `TierRechecker.aclose`'s
  "at most two control calls" true of the shipped stack and wrong of a deployment with GPU-placed
  peers.
- 2026-09-13: The four readings the trigger names were taken again and none has moved.
  `regain_residency` still makes two `host.status` calls and no `host.start`,
  [proto/body.proto](../../../proto/body.proto) still declares 16 RPCs with none an operator
  command, the control API still has four routes, and `evict_models` still defaults to the empty
  tuple in
  [config_swap.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/config_swap.py).
  The trigger has not fired.
- 2026-09-15: The four readings were taken again and none has moved. `regain_residency` still makes
  two `host.status` calls and no `host.start`, and its docstring still records the start as
  deferred; [proto/body.proto](../../../proto/body.proto) still declares 16 RPCs with none an
  operator command; the control API still offers four routes; and `evict_models` still defaults to
  the empty tuple. Nothing else reviewed that day touched this subject. The trigger has not fired.
- 2026-09-19: The four readings were taken again and none has moved. `regain_residency` still calls
  `host.status` twice and `host.start` never; [proto/body.proto](../../../proto/body.proto) still
  declares 16 RPCs, 11 on `BrainService` and 5 on `BodyService`, none an operator command; the
  control API in `api.py` still routes `/health`, `GET /models/{model}` and the start and stop
  posts; and `evict_models` still defaults to the empty tuple. `TierRechecker.aclose`'s docstring,
  which still said two control calls, was corrected to 2N + 2 later the same day. The 2026-09-17
  rule that refuses an evict list naming the cortex or the deep model leaves the 2N + 2 count
  unchanged, since N only ever counted peers. The trigger has not fired.
