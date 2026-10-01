# Readings: Qwen3.8-Flash-Next

Whether `Qwen3.8-Flash-Next-UD-Q3_K_XL`, the deep candidate of
[ADR-0004](../adr/ADR-0004-model-lineup.md) decision 8 that fits neither the card nor this
machine's memory, can serve the deep tier with most of its experts read from the models mount. The
conventions are those of [deep candidates](deep-candidates.md), which has the other candidates'
rows: VRAM above idle at ready, the SM clock as the median of `clocks.sm` over `clocks.max.sm`
across a row's busy readings, the power ceiling as `enforced.power.limit` over `power.max_limit`,
and a prediction in parentheses written into the backlog before the draw.

## The feasibility row, 2026-09-26

Placement `--n-cpu-moe 35 --threads 8` added to the tier's argv: every dense weight and the
experts of layers 35 to 47 on the card, the other experts and the n-gram table mapped from the
models mount, a 9p share. Floors written before the draw: ready within 300 s
(`CORTEX_SWAP_LOAD_TIMEOUT_S`), the first chunk of the 3400-word prompt within 120 s
(`CORTEX_INFERENCE_STALL_TIMEOUT_S`), and at least 7.5 tok/s over two draws of the decode probe at
`max_tokens` 128, thinking on, effort unset. Run A kept the model host's 24g cap; a watchdog written
just before it, and not in the backlog, removed the container after 520 MiB of host swap-out,
during the second decode draw and before the first-token draw. Run B, a departure, used a 20g cap
so that the host would not swap, leaving about 4 GiB less page cache.

| reading | 24g (run A) | 20g (run B) | floor | predicted | held |
| --- | --- | --- | --- | --- | --- |
| ready, `docker run` to health | 205.5 s | 141.2 s | 300 s: passes | 420 s (250 to 900) | no, below |
| decode, first draw (72-token prompt) | 5.07 tok/s | 3.48 tok/s | 7.5 tok/s | 0.8 (0.3 to 2.5) | no, above |
| decode, second draw (the prompt reused) | 13.35 over 74 tokens, cut | 7.54 tok/s | | | |
| first chunk of the 3400-word prompt | not drawn (run C) | none by the 240 s cut | 120 s: fails | over 240 s | yes |
| VRAM above idle at ready | 20,150 MiB | 20,655 MiB | | | |
| mount read a decoded token, first draw | 65 MB | 119 MB | | | |

The floors, as written: the load passes at both caps. The decode rule named two draws and not which
decides; each run's first draw is under 7.5 and its second, which reused the prompt and the experts
the first had paged in, is over it; run D settles it. The first-token floor fails at 20g: 4150 of
6184 prompt tokens were evaluated by 235.8 s, 2048 at a time in 91 to 131 s a step, which puts the
first token near 330 to 370 s (extrapolated). The 72-token prompt both runs evaluated took 61.3 s
at 24g and 59.2 s at 20g. Predicted, memory at the cap with pages read on every token: held. Predicted, the
row fails all three floors: not held, since the load passes.

The build loads `qwen4exp` and wrote coherent reasoning for 128 tokens after a short prompt; no
answer, tool call or sequence past 2048 tokens (the attention indexer's `top_k`) was drawn, and only
run B's server log survives to show no error line. The software power cap was never active: the card
drew about 40 W at an SM clock of 0.59 while the experts were read. The loads read 46.2 and 46.7 GB
from the mount (`read_bytes` in `/proc/1/io`, which counts mmap faults on this mount), at 225 and
330 MB/s, and the card's memory rose by about 19 GB only near the end of each load. Decode sped up
within a draw as the page cache filled (5.07 by quarters: 4.13, 4.43, 6.26, 6.21). At 24g the cgroup
filled its cap with file pages and host `MemFree` fell to 190 MiB: 521 MiB of idle pages were
swapped out and 1.3 MiB in, `MemAvailable` stayed at 24,000 MiB or more and the sampler was never
late. At 20g nothing was swapped out, and memory stall (`/proc/pressure/memory` full, 10 s) reached
26.5 against 10.5. The fit map drawn before the row
(`measurements/deep-2026-09-26/map-fit/flashfit.py`) assumed uniform routing and put the mount read
at 282 to 324 MB a token, 2.4 to 5 times what was measured; its decode bounds (2.0 to 2.5 tok/s on
the WSL side, 0.76 to 0.88 at a container's rate) are refuted, and with them its estimate of the
memory a host needs to hold every expert.

## The shipped cap, 2026-10-01

Two fresh loads on the same image (`sha256:952424b09abc`) with run A's argv, placement and 24g cap,
each under `scripts/memwatch.py`, with nothing else on the machine. Run C sent the 3400-word prompt
and run D the stop rows' Q2 as the only message, thinking on, effort unset, `max_tokens` 2000. Each
rule and prediction was written into R-735 before its draw.

| reading | run C | run D | floor | predicted | held |
| --- | --- | --- | --- | --- | --- |
| ready, `docker run` to health | 207.1 s | 136.2 s | 300 s: passes | | |
| first delta of the 3400-word prompt (6184 tokens) | 198.0 s, 1.65 of the bound | | 120 s: fails | fails, at 230 s or later | fails, yes; the time, no |
| first delta of Q2 (111 tokens) | | 75.4 s | | | |
| decode over the whole reply, deltas after the first | | 8.59 tok/s, 1996 deltas | 7.5 tok/s: passes | fails, at 7 (4.5 to 11) | no, above |
| SM clock during the request | 0.59 | 0.59 prompt, 0.69 decode | | | |
| power ceiling during the request | 0.87 | 0.88 prompt, 0.80 decode | | | |

Run C's prompt went in steps of 54, 2048, 2048, 1518, 496, 16 and 4 tokens, ended at 58.3, 146.4,
169.1, 181.6, 193.2, 197.1 and 198.0 s. The first full step took 88.1 s and read about 20.5 GB from
the mount; the second took 22.7 s and read about 3.9 GB, where every step at 20g read 26 to 36 GB.
So the 24g cap kept most of the experts one step reads and the 20g cap did not, and the first token waits
on reading them once. About 50 s into the request host `MemFree` rose by 16,288 MiB in 5 s as the
cgroup dropped file pages at its cap. Nothing was swapped out, `MemAvailable` stayed at 27,026 MiB
or more, memory `full avg10` peaked at 7.45 and the watchdog never woke late. The longest gap between
two `prompt_progress` chunks was 88.1 s.

Run D's server read 8.61 tok/s over 2000 tokens (`timings.predicted_per_second`), by quarters of
the reply 7.38, 10.64, 9.00 and 8.02; the reply reasoned coherently and was cut by `max_tokens`
before an answer. The decode read 71.8 GB from the mount, about 36 MB a token at 285 MB/s, and
`full avg10` peaked at 20.69. Its load read the same 46 GB in 0.66 of run C's time, so the host
side of the mount probably still held part of the file from run C; a decode drawn on a colder mount
may read slower.

Method: `measurements/deep-2026-09-26/flash-p2/` and `flash-p2-20g/` hold runs A and B (their
driver was not kept); `measurements/flash24-2026-09-28/flash24.py` drew run C and
`measurements/flash-decode-2026-10-01/decode.py` run D, each from the repo root, with its logs and
5 s card, mount and memory samples under `row/`.
