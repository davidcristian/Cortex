# The benchmark driver's cap leaves three CPU cells without a filled pass

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-20

The model baseline's driver, `tools/bench3.py` under `measurements/model-baseline-2026-11-16/`
(which git ignores), draws a CPU row in `cpu_model`. It reads the prompt rate from a probe of
2,000 tokens and draws the filled pass only when twice the prompt pass at that rate stays under
its cap of 400. A cell over the cap gets short prompts only, so it has no rate on a filled
context and its memory is read with the cache nearly empty.

## Reproduction

On 2026-11-20, CPU image build b10680, four threads: `python3 q8-probes/cpurow.py gemma-4-E4B
16384 f16 on` in that folder, and the same for the cells below. Each wrote a row with three
short prompts and no filled pass (lines 119, 120 and 123 to 125 of `bench/q8-ref.jsonl`, lines
575, 578 and 579 of `bench/q8.jsonl`):

- gemma-4-E4B at 16K and at 32K: at 16 bits with flash attention off and on, at 8 bits with it
  on;
- Qwen3.5-2B at 32K, at both cache types.

So [the readings](../../readings/kv-cache-remaining-cells.md) have no 8-bit over 16-bit rate on
a filled context for the default CPU subagent file above 8K. The cells that have one show the
prompt pass at 8 bits falling to 0.24 of the 16-bit one at 32K, which makes an 8-bit filled pass
there slower still.

## What to do

Give `cpu_model` an option that raises or removes the cap for named cells, and draw the three
cells at both types (gemma-4-E4B with flash attention off and on at 16 bits). Plan a whole
measurement session for it: the 8-bit filled pass of the smallest file at 32K took about a tenth
of one.

What would close it: a filled row for each of the three cells at both types in the readings, or
a line there saying why the tier does not need them (the CPU servers ship at 8K).

## History

- 2026-11-20: filed when the CPU rows of
  [R-1243](1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md) at 16K and 32K came
  back with short prompts only for three cells.
