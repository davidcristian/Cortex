# The alternate deep model has no rate row with one layer in RAM

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-24

The [model swap runbook](../../runbooks/model-swap.md) gives a deployment that names the alternate
deep model, gemma-4-31B's `UD-Q4_K_XL` file, and must stay inside the model budget at 16K the
setting `CORTEX_NGL_BRAIN=60`. The model host then writes `-ngl 60`, which keeps layer 0 in RAM,
and the tier read 18,107 MiB above the floor at its highest, inside the 18,177 MiB budget by
70 MiB ([readings](../../readings/kv-cache-deep-whole.md#other-shapes-at-the-budget)). What that
costs in rate is not drawn. The only split rows of this file are the engine's own fit with 8
threads, which kept 59 layers on the card at 16K and 8 bits and read 17,841 MiB, where `-ngl 59`
read 17,839: the file held whole at 12K wrote 1.54 times that split
([readings](../../readings/kv-cache-every-model.md#the-deep-tier-split-with-ram-gemma-4-31b-the-q4-file)).
One layer in RAM is a smaller split than that, and the model host writes no thread count, so the
engine picks its own.

A rate is drawn only on a night whose card power limit matches the baseline's. The row is the
deep tier as the model host starts it at 16K and `q8_0`, once at `CORTEX_NGL_BRAIN=60` and once
on its default, on one night, with the rate on a filled context, the short prompts and the prompt
pass as in the second draw of the readings, and the CPU load read beside it.

What would close it: both rows drawn on one night with a rule written before them, and the
runbook's sentence on the setting stating the ratio, or replaced by a different setting if the
split costs more than the rule allows.

## History

- 2026-11-24: filed when
  [R-1264](1264-gemma-4-31b-at-16k-is-over-the-model-budget-with-every-layer-on-the-card.md)
  closed with `CORTEX_NGL_BRAIN=60` in the runbook on memory rows alone, since no rate row was
  drawn that night.
