# Flash-Next's feasibility row is not complete at the shipped memory cap

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-26

Qwen3.8-Flash-Next was drawn against three floors: ready within `CORTEX_SWAP_LOAD_TIMEOUT_S`
(300 s), the first chunk of the 3400-word prompt within `CORTEX_INFERENCE_STALL_TIMEOUT_S` (120 s),
and at least 7.5 tok/s over two draws of the decode probe at `max_tokens` 128
([deep candidates](../../readings/deep-candidates.md#qwen38-flash-next-the-feasibility-row)). The
load passed at both memory caps tried. Two parts are not settled.

- **The first token at the shipped cap.** The run at the model host's 24g cap was stopped by a
  watchdog written just before it, which removed the container at 512 MiB of host swap-out, before
  the first-token draw. The swap-out was idle pages: `MemAvailable` stayed at 24,000 MiB or more
  and nothing waited on swap-in. The floor failed only at 20g, a departure made to keep the host
  from swapping. The 72-token prompt both runs evaluated took the same time at either cap, so a
  failure at 24g is the likely reading, not a measured one.
- **The decode floor names no deciding draw.** Each run's first draw read under 7.5 tok/s and its
  second, which reused the prompt and the experts the first had paged in, read over it. The rate
  also climbed inside each draw as the page cache filled, so 128 tokens say little about a reply
  thousands of tokens long.

What would close it, with the rule and a prediction for each written here before the draw:

1. The first chunk of the 3400-word prompt at `--memory 24g --memory-swap 24g`, under a watchdog
   that reads memory pressure (`MemAvailable`, `/proc/pressure/memory`, the sampler's lateness)
   rather than swap-out.
2. One fresh prompt decoded to its end or to 2000 tokens, the rate read over the whole reply, as
   the deciding decode draw.
3. The prompt's batch shape: every 2048-token step read most of the experts kept off the card, so
   `--batch-size` and `--ubatch-size` at the prompt's length may move the first token, at the cost
   of a larger compute buffer and fewer expert layers on the card.
4. One load at a higher log verbosity, to confirm the engine reads the n-gram table lazily, with the
   container's CPU use sampled against its 8-CPU quota.

If all three floors clear, the switch column, the stop row (its questions are in the readings) and
the injection row are priced from the measured decode rate and written here before they are drawn.
Beyond this machine, a host with memory for the paged experts, or the files on a local disk, which
[ADR-0004](../../adr/ADR-0004-model-lineup.md) decision 3 keeps on the mount, would change the
result; neither can be drawn here without the maintainer's decision.

## History

- 2026-09-26: filed by the deep candidates' measurement, whose other rows are published in
  [deep candidates](../../readings/deep-candidates.md); the gaps it left elsewhere are
  [736](736-the-deep-phase-sends-a-history-window-sized-for-the-cortexs-context.md) to
  [742](742-the-mixture-of-experts-rejection-rests-on-unrecorded-questions.md).
