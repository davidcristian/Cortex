# Flash-Next's feasibility row is not complete at the shipped memory cap

**Status:** done 2026-10-01
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Qwen3.8-Flash-Next was drawn against three floors: ready within `CORTEX_SWAP_LOAD_TIMEOUT_S`
(300 s), the first chunk of the 3400-word prompt within `CORTEX_INFERENCE_STALL_TIMEOUT_S` (120 s),
and at least 7.5 tok/s over two draws of the decode probe at `max_tokens` 128
([Qwen3.8-Flash-Next](../../readings/flash-next.md)). The load passed at both memory caps tried.
Two parts are not settled.

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

1. The first chunk of the 3400-word prompt at `--memory 24g --memory-swap 24g`, under `just
   mem-watch`, which reads memory pressure (`MemAvailable`, `/proc/pressure/memory`, its own
   lateness) rather than swap-out. The command, price, rule and prediction are in History.
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
- 2026-09-28: not queued in the unattended run of 2026-09-28. Its first row needs the watchdog on
  memory pressure written first, and at the 24g cap the container fills its cgroup with file pages
  on a machine of 31 GB, where CPU slots ran `just check` beside the card all night.
- 2026-09-28: the watchdog is `scripts/memwatch.py` under `just mem-watch NAME`. It removes the
  container when host `MemAvailable` falls under 2048 MiB, the memory `full avg10` share rises over
  50, or its own one-second sleep overshoots by 2 s, and it never reads swap-out. On the CPU, a
  container under a 3g cap allocating 64 MiB a step was removed at 1600 MiB held, against a floor
  set 1536 MiB under the host's available memory; the same container unwatched was ended by the OOM
  killer at its cap (`oom=true exit=137`). A 384 MiB container thrashing its page cache moved
  `full avg10` from 0 to 6.03 in seven seconds with 56 MiB held, so the pressure file counts stalls
  inside a container's own cap, which is why the limit sits above the 26.5 of the 20g run. The
  first driver was not kept (`flash-p2/` holds its logs only). The row's driver is now
  `measurements/flash24-2026-09-28/flash24.py`, which starts the watchdog itself; a CPU dry run on
  Qwen3.5-0.8B streamed a first delta for the 6142-token prompt. The command, run from the repo
  root when nothing else runs on the machine: `python3 measurements/flash24-2026-09-28/flash24.py`.
  Price: about 12 minutes of card (205 s to ready, a 360 s cut, teardown) and the machine's memory,
  since the cap is 24 GiB of this machine's 31 GiB: no detached run, no `just check` and no brain
  stack beside it. Rule: the floor passes when the first delta arrives within 120 s of the request.
  Prediction: it fails, with the first delta at 230 s or later or none by the cut. Each
  2048-token step at 20g read 26 to 36 GB from the mount at 274 to 279 MB/s, and the 24g cap holds
  3829 MiB more file pages, which can take about that much off a step; a first delta within 120 s
  would need over 630 MB/s from the mount. The second part is unchanged: no decode past 128 tokens
  has been drawn.
- 2026-10-01: item 2's row, written before its draw. The driver is
  `measurements/flash-decode-2026-10-01/decode.py`, run from the repo root with nothing else on the
  machine: a fresh load with item 1's argv and cap under the same watchdog, then the stop rows' Q2
  as the only message, thinking on, effort unset, `max_tokens` 2000, streamed, cut at 720 s. Price:
  about 15 minutes of card. Rule: the decode floor passes when the rate over the whole reply, the
  streamed deltas after the first over the time from the first delta to the last, is at least 7.5
  per second; the server's `timings` are read beside it. Prediction: it fails, at 7 per second (4.5
  to 11), the rate rising through the reply as the page cache fills. Run A read 65 MB from the mount
  a decoded token at 5.07 tok/s and its second draw 13.35, so a cache that keeps one topic's experts
  could clear the floor.
- 2026-10-01: done. Item 1, run C: the first delta of the 3400-word prompt came at 198.0 s at an
  SM clock of 0.59, so the first-token floor fails at the shipped cap. The predicted failure held
  and its 230 s bound did not, because the 24g cap kept most of the experts a 2048-token step
  reads, so the steps after the first took 12 to 23 s. Item 2, run D: 8.59 tok/s over a fresh
  2000-token reply at an SM clock of 0.69, so the decode floor passes and the predicted failure did
  not hold; its load took 0.66 of run C's time, so the mount was probably not cold. The whole row
  is now in [Qwen3.8-Flash-Next](../../readings/flash-next.md), and
  [ADR-0004](../../adr/ADR-0004-model-lineup.md) decision 8 states the shipped-cap result. Item 3
  and the rows after it move to
  [764](764-flash-nexts-first-token-is-undrawn-at-a-batch-the-length-of-the-prompt.md), and
  [763](763-the-stall-bound-times-a-whole-prompt-evaluation-as-one-silence.md) files counting
  progress chunks against the stall bound. Item 4 is declined: the load passes at 0.45 to 0.69 of
  its bound, and whether the engine reads the n-gram table lazily decides no floor.
