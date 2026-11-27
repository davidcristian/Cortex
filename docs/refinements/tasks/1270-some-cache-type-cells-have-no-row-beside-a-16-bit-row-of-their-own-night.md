# Some cache type cells have no row beside a 16-bit row of their own night

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-27

Every model the baseline of 2026-11-16 drew has rows at `q8_0` beside 16-bit rows of the same
night, and the cache type rule is applied to each in the readings
([the first](../../readings/kv-cache-types.md),
[2026-11-19](../../readings/kv-cache-every-model.md),
[2026-11-20](../../readings/kv-cache-remaining-cells.md),
[the deep tier](../../readings/kv-cache-deep-whole.md),
[Qwen3.8-Flash-Next](../../readings/kv-cache-flash-next.md)). The cells below are what those
records name as not drawn. Each belongs to a model whose result under the rule is fixed by other
rows, so no row here can change a tier's default: a row completes a ladder, replaces a figure
read from one launch, or gives a ratio at the fastest 8-bit draft length.

## Rows still to draw

Each command runs in `measurements/model-baseline-2026-11-16/tools/` with the RAM store up
(`HANDOFF.md` there has the two commands). 8-bit rows go to `bench/q8.jsonl`.

**Every night draws its own 16-bit pair.** Before the 8-bit rows of a cell, the same launch is
drawn at 16 bits into `bench/q8-ref.jsonl`, without drafting and at one draft length, and the
8-bit rows are divided by that pair only. The night's first and last launch is `python3
../q8-probes/drift.py`
([R-1259](1259-the-same-launch-reads-a-different-rate-on-another-night.md)).

1. **Qwen3.6-35B-A3B at 8 bits and draft length 3**, the fastest length on 2026-11-19, which has
   no row beside a pair of its night: `python3 bench3.py --models Qwen3.6-35B-A3B --kind moe
   --phase deep --nmax 2 --out q8-ref.jsonl`, then the same with `--kv q8_0 --nmax 3 --out
   q8.jsonl`. It answers which 8-bit length is the fastest in one night. The file writes 0.73 of
   its 16-bit rate without drafting, so it does not meet the rule at any reading.
2. **The CPU rows with a drafter at 16K and 32K, and the other draft lengths at 8K**: `python3
   bench3.py --models gemma-4-E4B,Qwen3.5-2B,Qwen3.5-0.8B --kind cpu --phase cpu --ctx 16384
   --out q8-ref.jsonl`, then the same with `--kv q8_0 --out q8.jsonl`, and for gemma-4-E4B both
   again with `--fa on`; then `--ctx 32768`, and no `--ctx` for 8K. Add `--fill-cap 0` for a
   filled pass of the three cells
   [R-1262](1262-the-benchmark-drivers-cap-leaves-three-cpu-cells-without-a-filled-pass.md)
   names. A CPU server keeps its cache in host RAM, so no row saves card memory.
3. **The Qwen3.5-0.8B CPU pair at 32K once more**, since 1.242 is one launch each: `python3
   ../q8-probes/cpurow.py Qwen3.5-0.8B 32768 f16 on`, then the same with `q8_0`. Write the pass
   mark first: the second pair inside 0.9 to 1.1 of 1.242.
4. **16-bit rows at the fastest 8-bit draft lengths.** gemma-4-26B-A4B at draft length 2:
   `python3 bench3.py --models gemma-4-26B-A4B --kind moe --ctx 32768 --phase deep --nmax 2 --out
   q8-ref.jsonl`, then the same with `--kv q8_0 --out q8.jsonl`, then both with `--ctx 65536`.
   Qwen3.8-27B at 64K at lengths 2 and 3: `python3 ../q8-probes/splitrow.py Qwen3.8-27B 65536 f16
   row <length> 600 <note>`, with the 8-bit row of the same length drawn that night.
5. **Qwen3.8-27B at 64K through the driver's own search**, and its 16-bit no-draft placement one
   step larger, once
   [R-1261](1261-the-benchmark-drivers-allowance-search-can-end-on-a-placement-that-does-not-fit.md)
   is done: `python3 bench3.py --models Qwen3.8-27B --kind moe --ctx 65536 --phase deep --nmax 1
   --out q8-ref.jsonl`, then the same with `--kv q8_0`, no `--nmax` and `--out q8.jsonl`. It
   replaces the upper readings 4.25 and 4.32.
6. **Qwen3.8-Flash-Next at draft lengths 3 and 4 at 16 bits**, which have 8-bit rows only:
   `python3 ../q8-probes/flash21.py row f16 3`, then `row q8_0 3`, then both with `4`. Staging
   this file empties the RAM store. **And the fit step at draft lengths 2 to 4**, where the 8-bit
   launches loaded 529 to 742 MiB less than the launch at length 1 with the same flags: add the
   lengths to `CELLS` in `../q8-probes/flashfit.py` and run it. It loads no weights and reads the
   placement the engine's fit ends on at each type.

Afterwards `python3 q8-report.py` rebuilds `q8.md`.

What would close it: each cell above either drawn and written into the readings record of its
model, or named there with the reason it needs no row. A cell can be settled alone; the task
closes with the last one.

## History

- 2026-11-21: filed when
  [R-1243](1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md) closed on
  Qwen3.8-Flash-Next's rows. Items 1 to 5 and 7 are that task's steps 2 to 7 with their
  commands, and item 6 is what the Flash-Next rows of 2026-11-21 left.
- 2026-11-27: the output check of the former item 7 was read from the recorded texts, and the
  [readings](../../readings/kv-cache-remaining-cells.md#whether-the-reply-changes) say the prompt
  states each clause that differs at 8 bits. Item 2 names the driver's new `--fill-cap` option.
  Items 1 to 5 and the rows of item 6 wait on rate rows, since the card's power limit read 175,
  not the baseline's 155. The fit step of item 6 reads no rate and did not fit this slot.
