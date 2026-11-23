# Nothing checks that the tiers the model host starts at boot fit the card

**Status:** done 2026-11-23
**Area:** inference-model-manager
**Origin:** [ADR-0053](../../adr/ADR-0053-model-host-supervisor.md)

At its boot the model host starts the cortex and every GPU subagent server in one pass
(`model_host_lifespan` in
[api.py](../../../brain/packages/model_manager/src/cortex_model_manager/api.py)). The pass does not
wait for the cortex to serve and does not read the card's free memory: the fit check
(`_refuse_a_load_the_card_cannot_hold`) is the deep tier's alone, and the spill watch reads the
deep phase's rate only. Settings that fill the card, such as a larger `CORTEX_CTX_SIZE`, therefore
load every server with no log line about memory.

Drawn on 2026-11-18 on the 24 GB card, the default stack with escalation on
([readings](../../readings/model-host-boot.md#a-server-that-keeps-exiting)). With
`CORTEX_CTX_SIZE=49152` the card read 18,390 of 24,463 MiB. With 400000 it read 23,324 MiB (the
engine's log gives the cortex's slot a context of 262144), all three servers answered `ready`,
no server exited, and neither the model host nor the brain logged a warning. An overcommitted pair also loads and answers `ready` on this card
([co-residency](../../readings/co-residency.md)), so `ready` does not say the settings fit. The
rate each tier decodes at with that context was not read.

A server that does exit at its load is loaded four times and then left stopped
([ADR-0054](../../adr/ADR-0054-baseline-residency.md) decision 9), so the open part is the load
that succeeds. The same decision says why no fit check runs before a boot load: no setting
declares what the cortex or a subagent server needs.

What would close it: once every boot tier answers `ready`, the pass reads the card and logs one
warning that names the free memory and each tier's context setting when the free memory is under
a set figure.

Next step: with `fit2.sh` in `~/.cache/cortex-run/2026-11-18/slot12/`, read the cortex's rate on a
filled context at `CORTEX_CTX_SIZE=400000` against the default, to choose the figure the warning
compares against.

## History

- 2026-11-18: filed from a reading of the host's boot pass beside the swap's fit check, and drawn
  the same day with a cortex context of 49152 and of 400000.
- 2026-11-23: done. The premise held in the code. The figure is the 1,536 MiB every reading of the
  card keeps free, a rule the budget already states, so no rate is needed to choose it:
  `BootFit` in `boot_fit.py` waits up to 600 s for every boot tier to answer ready, then logs one
  warning with the free and total MiB, the floor and each tier's `--ctx-size` when less is free.
  By the drawn figures the 400000 context leaves 1,139 MiB free and warns, 49152 leaves 6,073 and
  does not. Read on the card the same day: the 400000 roster left 890 MiB free and logged the
  warning once, the compose defaults logged the `INFO` line, and each free figure matched
  `nvidia-smi` ([readings](../../readings/model-host-boot.md#the-boot-fit-line)).
