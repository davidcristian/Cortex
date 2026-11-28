# The lineup recipe serves gemma-4-31B whole, and the card cannot hold that file beside the user's apps

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)
**Verified:** 2026-11-28

`scripts/switchlineup.py` serves every GPU pick with `-ngl 99 --ctx-size 8192` and a 16-bit cache.
The gemma-4-31B file the mount holds since 2026-11-16,
`unsloth/gemma-4-31B-it-qat-GGUF/gemma-4-31B-it-qat-UD-Q4_K_XL.gguf`, needed 18,621 MiB of the
card held whole at 6K of context with a 16-bit cache in the baseline's fit check of 2026-11-17
(`measurements/model-baseline-2026-11-16/bench/baseline.jsonl`), over the 18,177 MiB a model may
hold beside the user's apps ([model baseline](../../readings/model-baseline.md)). So `just
switch-lineup` cannot draw that row within the budget, and
[R-529](529-the-rendering-column-is-one-builds-measurement.md) leaves it owed on `b12375`.

The same file held whole at 12K with a `q8_0` cache needed 18,173 MiB, and the deep tier's cache
type defaults to `q8_0` (`DEFAULT_BRAIN_KV_CACHE_TYPE` in `cortex_model_manager/config.py`). A fix
gives a pick its own extra argv in `PICKS`, serves gemma-4-31B with `--cache-type-k q8_0
--cache-type-v q8_0`, checks with a fit row that its peak stays inside the budget at 8K, and draws
the row on the build the model host image then reads. A cache type changes no rendered prompt, so
the tail compares with the earlier rows directly, and the counts are read under R-529's rules.

## History

- 2026-11-28: filed by R-529, whose draw on `b12375` did not load the gemma-4-31B pick because its
  file does not fit the card whole at the recipe's argv.
