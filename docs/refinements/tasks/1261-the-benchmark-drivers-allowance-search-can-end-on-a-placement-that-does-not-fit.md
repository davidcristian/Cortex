# The benchmark driver's allowance search can end on a placement that does not fit

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-20

The model baseline's driver, `tools/bench3.py` under `measurements/model-baseline-2026-11-16/`
(which git ignores), draws a split model through the engine's fit. `moe_model` searches for the
allowance it passes as `--fit-target`: it runs placement checks and aims at a placement that
leaves 250 to 500 MiB above the 1,536 MiB reserve at load. `placement` in `q8-probes/rep.py` runs
the same search. When one step of the fit is wider than that 250 MiB window, the search moves
between two placements, neither inside the window, and can end on an allowance whose measured
launch does not fit. The driver then writes a check and no rates.

## Reproduction

Qwen3.8-27B, the Q4 file, at 64K and 16 bits without a drafter, on 2026-11-20 on build b12375:
`python3 q8-probes/rep.py Qwen3.8-27B 65536 f16` in that folder, with the RAM store up.

- The four placement checks loaded 17,993, 17,537, 17,993 and 17,545 MiB (lines 88 to 91 of
  `bench/q8-ref.jsonl`): one step of the fit is about 456 MiB here.
- The search ended on an allowance of 240. The measured launch loaded 18,216 MiB, left 1,497 MiB
  of the 1,536 needed, and wrote no rates (line 93).
- `python3 bench3.py --models Qwen3.8-27B --kind moe --ctx 65536 --phase deep --nmax 1 --out
  q8-ref.jsonl` uses the same search, so it would end the same way.

The rows of that cell were drawn with the allowance given by hand (`REP_ALLOWANCE=586` for
`rep.py`, an argument of `q8-probes/splitrow.py`), which is why
[the readings](../../readings/kv-cache-remaining-cells.md) call its ratios upper readings.

## A second defect in the same search

The first allowance for a drafted launch is 400 MiB plus a guess of 1,000 MiB for a drafter
inside the file. For Qwen3.8-27B that left 1,122 and 1,232 MiB above the reserve at load, where
the search aims at 250 to 500: the checks at 1,400 loaded 16,945 and 17,055 MiB, where 600 and
500 loaded 17,801 and 17,829 MiB.

## What to do

End the search on the last allowance whose check kept the headroom, and stop when two checks in
a row return a placement already seen. Start a drafted launch from the allowance the no-draft
search ended on plus the drafter's measured cost, not from a fixed guess. Then draw the cell
again through the driver and replace the upper readings
([R-1270](1270-some-cache-type-cells-have-no-row-beside-a-16-bit-row-of-their-own-night.md)
has the commands).

What would close it: the search changed in `bench3.py` and `rep.py`, and the Qwen3.8-27B cell at
64K drawn through it with a measured 16-bit row.

## History

- 2026-11-20: filed when the search did not settle for Qwen3.8-27B at 64K while the rows of
  [R-1243](1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md) were drawn.
- 2026-11-21: the commands for the cell are in
  [R-1270](1270-some-cache-type-cells-have-no-row-beside-a-16-bit-row-of-their-own-night.md)
  since R-1243 closed.
