# Qwen3.8-27B has no stop row at the shipped 16384 context

**Status:** done 2026-11-21
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

ADR-0004 decision 8 names `Qwen3.8-27B-UD-Q4_K_M` as the deep pick and says the stop counts do
not separate it from gemma-4-31B. Those counts were drawn on 2026-09-26 on engine build b10680,
with the server started by hand at `--ctx-size 8192` and no drafter
([deep candidates](../../readings/deep-candidates.md#the-stop-rows)): 10 of 12 at the template's
default effort, `xhigh`, and 12 of 12 at `medium` and at `low`. The deep tier is started
differently today:

- the context is 16384 (`CORTEX_CTX_SIZE_BRAIN`), where a draw that reasons to the end of the
  context has twice the room;
- the KV cache is `q8_0` (ADR-0077 decision 8);
- the model host runs build b12375;
- a deployment that names the file as its own drafter drafts with the layer inside it.

gemma-4-31B was drawn again at 16384 and stopped on 12 of 12
([the deep tier at 16384](../../readings/history-window.md#the-deep-tier-at-16384)).
Qwen3.8-27B was not.

## What to draw

The four written questions of the stop rows, three seeds each, on
`unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf`, with the deep tier started by the model
host on compose defaults (16384, one slot, `q8_0`), once without a drafter and once with
`CORTEX_MODEL_FILE_BRAIN_DRAFT` naming the same file. Each cell at the template's default effort,
and at `medium` and `low` sent as the request field `reasoning_effort`. Count the draws that
stop, the replies that are right by hand, and the reasoning tokens a draw spends at the median.
Write the prediction for each cell into this file before the first launch.

The drivers are the stop-row scripts of the first draw, `phase1.py` to `phase5.py` over
`questions.py` in `measurements/deep-2026-09-26/q27-drivers/`, which git ignores. They start a
server by hand; point them at the model host's deep tier, started over the control API as
`q8-probes/deepwhole.py` in `measurements/model-baseline-2026-11-16/` starts it.

What would close it: the rows added to the stop rows of deep candidates, and ADR-0004 decision 8
changed where it says no stop count was drawn at 16384, or the decision reopened if `xhigh` reads
apart from gemma-4-31B's 12 of 12.

## Prediction

Written on 2026-11-21 before the first counted draw. Against gemma-4-31B's 12 of 12 a cell reads
apart, by the stop rows' two-sided Fisher test at p below 0.05, only at 7 of 12 or fewer.

| cell | stops of 12 (range) | reasoning tokens a draw, median (range) |
| --- | --- | --- |
| draft layer, `xhigh` (nothing sent) | 11 (9 to 12) | 2200 (1700 to 3000) |
| no drafter, `xhigh` (nothing sent) | 11 (9 to 12) | 2200 (1700 to 3000) |
| no drafter, `medium` | 12 (11 to 12) | 1350 (1000 to 1900) |
| draft layer, `medium` | 12 (11 to 12) | 1350 (1000 to 1900) |
| no drafter, `low` | 12 (11 to 12) | 1100 (800 to 1600) |
| draft layer, `low` | 12 (11 to 12) | 1100 (800 to 1600) |

- **The misses.** Both 8192 misses at `xhigh` were Q4 draws. Predicted: at most one Q4 draw in
  each `xhigh` cell reasons to the end of the 16384 context, and no draw of Q1 to Q3 does.
- **The drafter.** Predicted to change no count by more than one draw at any effort, and to
  change the text of most replies, because a drafted launch decodes in batches of another size.
  The null result is the same count, within one draw, in both cells of an effort.
- **The effort field.** Predicted: `reasoning_effort` as a top-level request field changes the
  rendered prompt on b12375 as it did on b10680.

A cell the time box does not reach is named as not drawn.

## History

- 2026-11-20: filed when the maintainer made Qwen3.8-27B the deep pick on its fit inside the
  model budget. The stop counts the decision calls level were drawn at 8192.
- 2026-11-21: drawn on build b12375 as the model host starts the tier, at 16384 and `q8_0`. At
  `xhigh` the pick stopped on 11 of 12 without a drafter and 12 of 12 with its draft layer; at
  `medium` without a drafter on 12 of 12, and at `low` with the layer on 12 of 12. No cell reads
  apart from gemma-4-31B's 12 of 12, and every prediction for those four cells held
  ([readings](../../readings/deep-candidates.md#the-stop-rows-at-16384)). The drafted `medium`
  cell got 7 of its 12 draws here, all stopped, and its other 5 on a later launch of the same
  date ([readings](../../readings/deep-effort.md#the-drafted-medium-stop-cell)). The undrafted
  `low` cell was not drawn: the second drafted launch drew `low` first so that each effort had
  a whole cell. ADR-0004
  decision 8 now gives the 16384 counts. Filed:
  [R-1271](1271-no-stop-row-is-drawn-beside-a-full-handoff-prompt.md), for the draws that
  generated more than a full handoff prompt leaves.
