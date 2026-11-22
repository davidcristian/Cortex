# The first request after a deep load takes a fixed time no row explains

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-22

A handoff loads the deep tier and sends it one request. On 2026-11-22 that first request's
prompt pass took a fixed time more than a second request's of the same size, on both files of
the deep pick and at both prompt sizes drawn
([readings](../../readings/nvfp4-deep-pair.md#the-deep-turn-of-a-handoff)). For the Q4 file,
the one ADR-0004 names, the fixed time is 4.0 times a later prompt pass over 896 tokens, so
the first token of a short handoff comes 5.0 times as late as a later request's would. For the
NVFP4 file the fixed time is 2.03 times the Q4 file's.

What is not known:

- What the engine does in that time. The rows time the request and read no engine log line
  for it.
- Whether it belongs to the draft layer. Every row of that record started the tier with the
  file's own draft layer at `--spec-draft-n-max 3`. The stop cells have one draw that says it
  does not: the first counted draw of each file's launch without a drafter, the NVFP4 file's
  `medium` cell of 2026-11-22 and the Q4 file's `xhigh` cell of 2026-11-21, has a prompt pass
  of 266 and 304 tokens that took 0.98 and 1.11 of that file's fixed time. One draw a file on
  another prompt is not a row drawn for it.
- Whether a request the model host sends before it reports the tier ready would take that
  time out of the first token. It would add the same time to the load, so the whole deep turn
  of a handoff would not change, only how long the deep request waits for its first token.

What would close it: the first and the second request after a load on the Q4 file with and
without its draft layer, three loads each, with the engine's log read for the first request,
and a written reading of whether the time can be removed or only moved into the load.

## History

- 2026-11-22: filed by the rows of both Qwen files' first request after a load, which
  [R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md)
  compares the two files on.
