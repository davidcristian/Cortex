# The Qwen NVFP4 file has no injection row at xhigh and no undrafted xhigh stop cell

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a History line in task 1244 recording a choice that names the Qwen NVFP4 file for the deep pick.
**Verified:** 2026-11-22

The deep tier reasons at `medium` by default, and a deployment that sets
`CORTEX_REASONING_EFFORT_BRAIN` to an empty value reasons at the template's own `xhigh`. The
pick's Q4 file has rows at both levels from 2026-11-21. The Qwen NVFP4 file has its `medium` rows
and one `xhigh` cell from 2026-11-22
([what the Qwen NVFP4 file writes](../../readings/nvfp4-deep-counts.md)):

| row at `xhigh`, nothing sent | Q4 file | NVFP4 file |
| --- | --- | --- |
| stop cell, draft layer | 12 of 12 stopped | 11 of 12 stopped |
| stop cell, no drafter | 11 of 12 stopped | not drawn |
| injection text row, draft layer | 0 framed and 0 control obeyed, of 100 each | not drawn |
| injection text row, no drafter | 0 and 0 | not drawn |
| a literal `</think>` in a control reply of those rows | 11 and 13 of 100 | not drawn |

What is not known:

- Whether the NVFP4 file writes a literal `</think>` into a reply at `xhigh`, as the Q4 file does
  ([R-1273](1273-a-deep-reply-can-hold-a-literal-think-tag-and-its-text-twice.md)). At `medium`
  neither file wrote one in 200 draws.
- Whether its undrafted `xhigh` cell stops as often as the Q4 file's.
- Whether its drafted `xhigh` draws run longer than the Q4 file's. 6 of its 12 generated more
  than the 5521 tokens a full history window leaves at 16384, against 1 of the Q4 file's 12
  (two-sided Fisher p 0.069), and its three Q2 draws account for three of the six. The
  comparison was not written down before the draw, so it is a reason to draw the cell again and
  not a reading.

What would close it: the three undrawn rows drawn as the Q4 file's were, with the count that
reads apart written first, and the drafted `xhigh` stop cell drawn again with a mark for the
draws over 5521 tokens written first. The drivers are `stop16.py` and `inj16m.py` in
`~/.cache/cortex-run/2026-11-22/v1/`; `inj16m.py` sends `medium` and needs the field removed.
None of it is wanted while the pick names the Q4 file.

## History

- 2026-11-22: filed when
  [R-1245](1245-the-nvfp4-files-have-none-of-the-rows-the-deep-pick-is-compared-on.md) drew the
  Qwen NVFP4 file's rows at `medium` and the time box reached one `xhigh` cell.
