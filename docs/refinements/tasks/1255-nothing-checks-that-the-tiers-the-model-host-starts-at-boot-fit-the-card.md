# Nothing checks that the tiers the model host starts at boot fit the card

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0053](../../adr/ADR-0053-model-host-supervisor.md)
**Verified:** 2026-11-18

At its boot the model host starts the cortex and every GPU subagent server in one pass
(`model_host_lifespan` in
[api.py](../../../brain/packages/model_manager/src/cortex_model_manager/api.py)). The pass does not
wait for the cortex to serve and does not read the card's free memory: the fit check
(`_refuse_a_load_the_card_cannot_hold`) is the deep tier's alone, and the spill watch reads the
deep phase's rate only. Settings that leave no room for the last server, such as a larger
`CORTEX_CTX_SIZE`, therefore have two outcomes, and neither is reported as a fit problem:

- On a card that pages an overcommit to system memory
  ([co-residency](../../readings/co-residency.md)) every server loads and answers its health
  check, so the lease probe reads it as serving, and each tier decodes at a lower rate with no log
  line.
- On a card that fails the load, which server exits depends on the order the loads finish, and it
  can be the cortex, since the servers load beside it and not after it as in the brain's boot
  recovery. The host starts the exited server three more times and leaves it `failed`. With
  escalation on, the brain's recheck pass then sends a `start` at every interval
  (`DEFAULT_TIER_RECHECK_INTERVAL_S`), and each `start` gives the restart budget back.

The second outcome's count was reproduced in process on 2026-11-18 with the real `ModelSupervisor`
over fake child processes that exit at every load: each `start` asked for led to 4 loads and then
`failed`, for three `start`s in a row. The first outcome was not drawn, because it needs the card
overcommitted on purpose.

What would close it: the boot pass reads the card after each tier serves and logs a warning that
names the tier and its settings when the free memory is under a set figure, or the settings
declare each tier's figure as `CORTEX_SWAP_BRAIN_VRAM_MIB` does for the deep one and the pass
refuses the tier that does not fit. For the loop, a restart budget that an asked `start` gives
back only once the tier has served.

## History

- 2026-11-18: filed from a reading of the host's boot pass beside the swap's fit check.
