# The free memory the deep tier needs beside a peer is unmeasured

**Status:** done 2026-09-23
**Area:** inference-model-manager
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)

The [model-swap](../../runbooks/model-swap.md) runbook sets `CORTEX_SWAP_BRAIN_VRAM_MIB` on the
24 GB card at 20125 MiB: the plain deep tier's 19125 MiB plus a gigabyte for the desktop's share of
the card. Only two readings bound the figure. Beside the E4B subagent tier the deep tier spilled
with 19541 and 19549 MiB of `memory.free` before the load, decoding at 0.36 and 0.62 of its solo
rate, and alone it fits with about 22875 MiB free. So the gigabyte is slack rather than a measured
margin, which ADR-0055 decision 2 calls one more unchecked number. The spill itself is not
explained: beside the peer the deep tier added 186 and 195 MiB less to the card than alone,
although `memory.free` was over 400 MiB above its cost, while stacked E4B tiers used the card down
to 277 MiB free. The readings are in [co-residency](../../readings/co-residency.md).

**What would close it.** Load the plain deep tier beside fillers of known size, a small model at
chosen context sizes, that leave `memory.free` between 19549 and 22875 MiB before the load; read
decode against a solo start at matched clocks, and `nvidia-smi` every second through the load to
see what the deep tier holds above its at-ready size. Then set the runbook's figure at the lowest
free reading that decodes at the solo rate, plus the idle floor's movement. A peer small enough to
fit beside the deep tier would restore co-residency on this card, and that is a model pick for the
maintainer, not this task.

## Registration, written 2026-09-22 before the first deep start

- **Deep tier.** Every start runs the plain tier's shipped argv on `server-cuda` `952424b09abc`,
  `-ngl 99 --ctx-size 8192 --parallel 1 --jinja --cache-ram 0`, plus `-lv 4` for the buffer sizes
  and llama.cpp's own free-memory reading, in every start alike.
- **Filler.** `Qwen3.5-0.8B-Q8_0` in `llama-server`, `-ngl 99 --parallel 1 --cache-ram 0`, idle
  beside the deep tier. Calibrated at 21:33 with no deep start: 1181 MiB above the floor at
  `--ctx-size` 4096 and 2804 at 131072. Rungs by that line, as the `memory.free` each should leave
  at a floor of 1850 MiB: ctx 4096 (21106), 45056 (20583), 81920 (20111), 94208 (19954), 106496
  (19797), 131072 (19483). The reading that counts is the one taken, not the prediction.
- **Order.** `solo-a` (deep alone), then 81920. A fit steps down one rung and a spill up one, until
  a fitting rung sits next to a spilling one or the rungs run out. If every rung down to 106496
  fits, 131072 runs as the control that the spill is not particular to the E4B peer. `solo-b`
  last. No new start begins after 22:35; rungs not drawn are named in this task.
- **Per start.** `nvidia-smi` every second from before the first container to removal; `memory.free`
  read immediately before the deep start is that row's free figure. One reasoning prompt, thinking
  on, `max_tokens` 256, seed 42, one warm-up and three timed requests; the rate is
  `timings.predicted_per_second`, the clock the median `clocks.sm / clocks.max.sm` over samples
  inside the timed requests with utilization at 50 or more. Containers are removed and the card
  left idle 20 s between starts. No other GPU or CPU work runs.
- **Deciding rule.** S is the lower of the two solo medians (solo-a alone if solo-b is not drawn).
  A row fits when its median is at least 0.95 S; it spills when its median is under 0.90 S and its
  clock is not more than 0.05 under solo-a's; anything else is reported as undecided. N is the
  lowest free figure of a fitting row, set only if no row with a higher free figure spilled.
- **The figure.** `CORTEX_SWAP_BRAIN_VRAM_MIB` becomes N plus the largest movement of the idle
  floor recorded inside one session on this card (1307 MiB on 2026-08-07, or more if this draw's
  idle readings move further), rounded up to 25 MiB. With no N it stays at 20125.
- **Prediction.** The spilled pair stopped at about 600 MiB of `memory.free` at ready with 186 MiB
  of its buffers missing from the card, so N is near 19117 plus 600, and the 81920 and 106496 rungs
  fit while 131072 spills.
- **Repeats, added at 21:46 after four starts and before the fifth.** The 94208 rung fit at 20037
  MiB free and the 106496 rung spilled at 19967, so the order stopped there. Both run once more,
  106496 first, then `solo-b`. The deciding rule covers the repeats as rows.
- **Amendment, written 2026-09-23 at 00:58, after a stop at 21:50 and before any later start.**
  The 106496 repeat finished; the 94208 repeat was stopped after its warm-up, so it counts as its
  at-ready memory reading and has no rate; `solo-b` was not drawn. The idle floor read 3339 MiB
  used and 20799 `memory.free` at 00:55, 1649 MiB above 21:48's 1690, so the 21:4x rows are
  judged against `solo-a` alone and the rows from here against the lower of `solo-c`, drawn
  first, and `solo-d`, drawn last. At this floor the filler's smallest registered size leaves about
  19620, so it is recalibrated with fewer offloaded layers, with no deep start, to leave about
  20300, 20040 and 19960; the configurations are written here before the first of them runs. Order:
  `solo-c`, 20040, 19960, 20300, then repeats of 20040 and 19960 while time allows, then `solo-d`.
  No start begins after 02:15.
- **The figure term, amended at the same time.** The check reads the floor's level in
  `memory.free`, so only a rise between that reading and the end of the load reaches the deep
  tier. The registered term measures a change of level instead: N plus tonight's 1649 would be
  about 21700 and would refuse the solo load at 00:55's own 20799, which fits by the same
  readings. The term becomes R, the largest rise of `memory.used` inside any 100 s of this draw's
  one-second samples taken with none of its containers running, 100 s being the longest deep load
  (97.5 s). The figure changes only when N plus R differs from 20125 by more than the gap between
  the lowest fitting and the highest spilling free figure, the draw's resolution.
- **Filler, amended at 00:59 before `solo-c`.** The floor fell from 3339 to 2042 MiB between 00:55
  and 00:59 with only filler calibrations running, so the registered filler reaches every target
  again and stays: `-ngl 99` at ctx 51200 (about 20300 free), 72704 (20040) and 77824 (19960).
- **Order, amended at 01:06 after `solo-c` and two rungs.** The floor keeps moving by 50 MiB
  between starts, so the 19960 rung read 20051. From here each start's ctx is computed from the
  idle `memory.free` read just before it, by the filler's measured line (2033 MiB at ctx 72704
  plus 0.01278 MiB a token), to reach its target. Order: 20300, then 19960 and 20040 alternately,
  then 20000 twice, `solo-d` last, no start after 02:15.
- **Order, amended at 01:21 after three more rows.** Every row since `solo-c` fit, three of them at
  19960 to 19963 MiB free, where both 21:4x rows spilled, so 20000 tells nothing. In its place a
  ladder descends from 19860 in 100 MiB steps until a row spills; that rung runs once more, the one
  above it once more, then `solo-d`.

## History

- 2026-09-22: opened by the finding that the E4B tier did not grow between the August and
  September builds (3286 and 3293 MiB, the same buffers on both) and that the pair read as a fit
  in August already filled the card, which the runbook now answers by leaving co-residency off on
  a 24 GB card.
- 2026-09-23: done. Eighteen deep starts beside an idle filler, one stopped after its warm-up, and
  three alone, in two sessions three hours apart: every timed start at 20037 MiB free or more
  decoded at the solo rate, one of them at 0.94 of it at a lower clock, every one at 19763 or less
  spilled, and 19962 and 19967 spilled in the first session while 19960 to 19963 fit three times in
  the second. So no N and the figure stays at 20125, which clears every spill seen by 158 MiB; the
  runbooks now give that reason in place of a gigabyte of floor slack. A 19664 start ran past the
  ladder's stop and spilled. The shortfall is in the buffers allocated after the model buffer while
  the card reads most of a gigabyte free, and the driver's placement rule is not readable from WSL.
  The command-line digest named when the drafter task closed is a rejected alternative in
  [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md); the readings are in
  [co-residency](../../readings/co-residency.md).
