# Qwen3.8-27B has no stop row at the shipped 16384 context

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-20

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

## History

- 2026-11-20: filed when the maintainer made Qwen3.8-27B the deep pick on its fit inside the
  model budget. The stop counts the decision calls level were drawn at 8192.
