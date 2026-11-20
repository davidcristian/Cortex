# gemma-4-31B at 16K is over the model budget with every layer on the card

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-20

The model host starts the deep tier at 16K with every layer on the card. `llama_server_argv` in
[tiers.py](../../../brain/packages/model_manager/src/cortex_model_manager/tiers.py) always
writes `-ngl` (99 from `CORTEX_NGL_BRAIN`) and never `--fit` or a thread count, so the engine
moves no layer and a tier that does not fit spills into host RAM with no error
([model swap measurements](../../runbooks/model-swap-measurements.md)). Qwen3.8-27B's Q4 file is
inside the model budget in that shape (ADR-0004 decision 8). gemma-4-31B's Q4 file is over it at
both cache types, so a deployment that names it starts a tier over the budget, and no setting
gives it a shape inside the budget at 16K. The tier's default type is `q8_0` (ADR-0077 decision
8), which takes less and is still over.

## What the rows show

Drawn on 2026-11-20, twice, on engine build b12375, each launch through the model host
([readings](../../readings/kv-cache-deep-whole.md)). With the desktop's apps counted as 4,750 MiB
and 1,536 MiB kept free, models get 18,177 MiB.

- **Neither type fits the budget at 16K.** `q8_0` is over it by 198 to 207 MiB without the
  drafter and 907 to 909 MiB with it; `f16` by 1,266 MiB and 1,597 MiB in the second draw. No
  row has a spill's rate: the desktop's apps held 3,221 to 4,247 MiB, under the 4,750 MiB the
  budget counts. At 8 bits the file fits the budget whole at 12K without its drafter and at no
  context with it.
- **`f16` with the drafter is at the card's limit**: 23,085 and 23,057 MiB of 24,463 at the
  highest reading, with about 310 MiB of the launch not accounted for on the card in the second
  draw. Its rate is not a spill's (0.97 and 0.98 of the `q8_0` row), and a small spill is not
  ruled out. A deployment that sets `f16` and names the drafter starts that shape.
- **The engine's own fit is faster on this file and no setting reaches it.** Split by the
  engine's fit the file writes 2.08 to 2.11 times its 16-bit rate at 8 bits
  ([the rows of 2026-11-19](../../readings/kv-cache-every-model.md)).

## What to decide

Which of these a deployment of gemma-4-31B gets, on rows drawn for each: a smaller deep context (the deep context
equals the cortex's today, because both phases read one history window), a placement setting
that lets the engine fit the tier, or a budget counted for a tier that is alone on the card.

## Rows not drawn

Each launch is `python3 q8-probes/deepwhole.py <label> f16|q8_0 none|mtp [note]` in
`measurements/model-baseline-2026-11-16/`, with the stack files of
`~/.cache/cortex-run/2026-11-20/` (compose project `cortexn25`); `bash
~/.cache/cortex-run/2026-11-20/deep-stop.sh` removes the project afterwards.

1. The drafted pair at 8K, where neither type is at the card's limit, to see whether `f16` keeps
   the 1.10 lead it has without the drafter.
2. The four launches with the desktop's apps at 4,750 MiB or more, the load the budget counts.

What would close it: the context or placement of a gemma-4-31B deep tier at 16K decided on rows
and recorded in the model-swap runbook, with a setting added if the decision calls for it, or
the reason recorded that the shape stays.

## History

- 2026-11-20: filed when
  [R-1260](1260-the-deep-picks-file-has-no-cache-type-row-in-the-shape-the-stack-starts.md)
  closed with the deep tier's default set to `q8_0`: its draw showed no shape of gemma-4-31B at
  16K inside the budget at either type.
