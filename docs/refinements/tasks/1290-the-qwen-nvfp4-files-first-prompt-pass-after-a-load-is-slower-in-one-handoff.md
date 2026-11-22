# The Qwen NVFP4 file's first prompt pass after a load is slower in one handoff

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-22

A handoff's first token waits on the deep server's first prompt pass after its load. In the one
handoff drawn on the Qwen NVFP4 file, on 2026-11-22, that pass took 0.050 of
`CORTEX_INFERENCE_STALL_TIMEOUT_S` for 861 prompt tokens
([readings](../../readings/nvfp4-deep-counts.md#a-handoff-through-the-brain)). The Q4 file's
drafted handoffs of 2026-11-21 took 0.027 to 0.028 for 861 or 899 tokens
([readings](../../readings/model-swap.md#a-handoff-on-the-deep-pick)). That is 1.8 times as
long, on one draw and on rows of two dates.

The rate rows read the other way: on a filled context the NVFP4 file's prompt pass runs at 1.8
times the Q4 file's rate ([readings](../../readings/nvfp4-deep-pair.md)). Those rows time a
prompt on a server that has answered a request before, so the two readings can both be true,
and no row says which one a handoff gets.

What is not known:

- Whether the first request after a load is slower on the NVFP4 file when both files are drawn
  on one date.
- Whether the difference is a fixed time before the first token or grows with the prompt. A
  handoff with a full history window sends a prompt more than twelve times as long as this one.

What would close it: both files started as a handoff starts them on one date, the first request
after each load timed at this prompt and at one the size of a full history window, three loads
each, with the difference that reads apart written first. The result goes into the NVFP4
record's handoff section and into
[R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md), which
compares the two files.

## History

- 2026-11-22: filed by the handoff of
  [R-1245](1245-the-nvfp4-files-have-none-of-the-rows-the-deep-pick-is-compared-on.md) on the
  Qwen NVFP4 file, whose prediction for the first token missed.
