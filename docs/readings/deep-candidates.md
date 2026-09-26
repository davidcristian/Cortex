# Readings: deep candidates

The rows the deep pick of [ADR-0004](../adr/ADR-0004-model-lineup.md) (decisions 5, 8 and 14) is
compared on for the two Qwen3.8 candidates, with the pick and the alternate redrawn beside them.
The 2026-08-04 rows of the first four candidates are in [model lineup](model-lineup.md), the
switch tails in [thinking switch](thinking-switch.md) and the injection counts in [injection text
rows](injection-text-rows.md). VRAM is `nvidia-smi` `memory.used` at ready less the same card read
just before the start. Beside each wall clock and rate are the SM clock, the median of `clocks.sm`
over `clocks.max.sm` across the row's busy 5 s readings, and the power ceiling,
`enforced.power.limit` over `power.max_limit`. A prediction in parentheses is the median and 90%
range written into the backlog before the draw, and each is marked held or not.

## How the rows were drawn

**2026-09-26**, llama.cpp `server-cuda` `b10680-d7bd3bfca` (`sha256:952424b09abc`), read off
`/props` on every load but the drafter row's three, whose logs print no build line and whose image
digest was the same. One server on the card at a time, started by hand with the argv
`ModelHostConfig(...).tiers()` builds for the deep tier
(`-ngl 99 --ctx-size 8192 --parallel 1 --jinja --cache-ram 0`, no reasoning budget, no drafter)
under the model host's caps (`--cpus 8 --memory 24g --memory-swap 24g`), not through the model host
daemon. The request is `build_payload` as the deep phase sends it with the default bounds: thinking
on, streamed, no `max_tokens`, no sampler field and no `reasoning_effort`, so Qwen3.8 runs at its
template's default effort, `xhigh`, and every model at the engine's sampler. `/props` read
temperature 1.0, top_k 20, top_p 0.95 and min_p 0.05 on every Qwen load (the model cards say min_p
0.0), and 1.0, 64, 0.95 and 0.05 on the pick. A row that departs names the field it adds. The pick,
`gemma-4-31B-it-qat-q4_0`, runs with no drafter, as it ships. Every load ran at an SM clock of 0.59,
reading the models mount. Logs and drivers: `measurements/deep-2026-09-26/`, which git ignores.

## The candidates side by side

Ratios are of the pick's own figure unless a bound is named.

| reading | gemma-4-31B (pick) | Qwen3.8-27B UD-Q4_K_M | Qwen3.6-27B Q4_K_M (alternate) | Qwen3.8-Flash-Next UD-Q3_K_XL |
| --- | --- | --- | --- | --- |
| artifact | 17.65 GB, QAT | 16.46 GB | 16.82 GB | 89.98 GB in three files |
| VRAM above idle, 8192 context | 19,138 MiB | 15,744 to 15,770 MiB | 16,417 MiB | 20,150 to 20,655 MiB, the rest paged from the mount |
| ready, of the 300 s load bound | 0.32 | 0.29 the first time, 0.20 to 0.22 after | 0.32 | 0.47 to 0.69 |
| stop row: stopped, right by hand, of 12 | 11, 10 | 10, 10 at `xhigh`; 12, 10 at `low`; 12, 11 at `medium` | 10, 9 | not drawn |
| reasoning tokens a stop-row draw, median | 1434 | 2189 `xhigh`, 1122 `low`, 1357 `medium` | 4118 | not drawn |
| stop-row wall a draw, median | 1.0 | 1.28 `xhigh`, 0.78 `low`, 0.97 `medium` | 2.36 | not drawn |
| decode | 1.0 | 1.01, at SM 0.50 against 0.59 | 1.02 on the stop draws, at SM 0.46 against 0.57 | 0.09 to 0.14 on a fresh prompt |
| first chunk of the 3400-word prompt, of the 120 s stall bound | 0.037 (4018 tokens) | 0.040 (6184 tokens) | not drawn | none within twice the bound (20g cap) |
| injection, framed and control obeyed of 100 | 0 and 8 (2026-09-24) | 0 and 0 | not drawn | not drawn |
| multi-token prediction | a separate drafter file, 1.34 to 1.89 times plain | a built-in layer, 1.16 to 1.43 times plain, which no setting names | not drawn | none in the artifact |
| template | | `xhigh` unless sent; empty thoughts before earlier replies | drops a third leading system message, which the adapter now joins ([ADR-0071](../adr/ADR-0071-leading-system-messages.md)) | the 27B's, byte for byte |

The pick's stop-row draw took 58 s at the median and its decode probe read 37.15 tok/s
(`timings.predicted_per_second`), the figures the ratios divide by.

## Qwen3.8-27B

**Serving and the template.** Ready in 87.1 s the first time and 61.2 to 64.5 s on the next four
loads of the same shape (engine start to `listening`); predicted 93 to 116 s cold, not held, and
about two thirds of that warm, held (0.72). Whether the first load was cold cannot be seen from WSL:
16.46 GB in 87.1 s is at least 189 MB/s, above the 142 to 177 MB/s of the 2026-08-04 cold loads.
VRAM 15,762 MiB, 12 more after a request (predicted 15,800, 15,300 to 16,500, held); min_p 0.05 on
`/props` (predicted, held). `chat_template_caps` reports object arguments, preserve reasoning,
reasoning effort, tools and the system role. `POST /apply-template` shows:

- the tier's request ends in an open `<think>\n`, with the `xhigh` sentence in the system prompt;
  `enable_thinking: false` ends in a closed empty thought with no effort sentence, under
  `REPLY_ENVELOPE` too;
- `reasoning_effort` `medium` adds no sentence and `low` its own; `max`, an engine value, returns
  HTTP 500 from `/apply-template` and from `/v1/chat/completions`, since the template raises;
- with `preserve_thinking` left on, each earlier assistant reply renders behind an empty
  `<think>\n\n</think>`, the brain storing no reasoning; `preserve_thinking: false` removes it;
- the deep phase's three leading system messages (preamble, memory, recap) all render, merged;
- the harness's `read_file` round trip with its arguments as a JSON string renders (200), the
  engine parsing them before the template sees them.

**Rates**, each the median of 3, the pick drawn 25 minutes later:

| reading | Qwen3.8-27B over the pick | predicted | held | SM, ceiling (Qwen; pick) |
| --- | --- | --- | --- | --- |
| decode probe (`test_decode_cadence_live.py`, thinking on) | 1.01 | 1.0 (0.9 to 1.15) | yes | 0.50, 0.89; 0.59, 0.90 |
| first streamed delta, 3400-word prompt, `max_tokens` 16 | 1.09 | 0.8 to 1.3 | yes | as above |
| share of round 2's prompt evaluated, two-round tool loop | 0.16 (pick 0.23) | 0.9 to 1.0 | no | as above |

The decode probe asks for about 120 words: Qwen3.8 generated 1545 to 2063 tokens, the pick 409 to
635, so equal rates are not equal waits. The 3400-word prompt of `tierarm.py` is 6184 Qwen tokens
against 4018 gemma tokens and Qwen evaluated it 1.38 times as fast; the prompt repeats 24 rare
words, so the token ratio says nothing of ordinary text. In the tool loop round 1 (631 tokens)
ended in a `read_file` call on every draw, and round 2 evaluated 115 to 119 tokens with `cache_n`
627: the engine reused the slot's prefix on the hybrid model under `--cache-ram 0`, at a length far
short of the context.

**Footprint and the projector**, one load each, decode as a ratio of the 8192 shape's:

| shape | VRAM above idle | predicted | held | decode, one reply (SM) |
| --- | --- | --- | --- | --- |
| `--ctx-size` 16384 | 16,273 MiB | 512 more than at 8192 | yes (503 to 529 more) | 1.01 (0.51) |
| `--ctx-size` 32768 | 17,354 MiB | 1,536 more | no (1,584 to 1,610 more; 67.6 KiB a token past 16384) | 1.02 (0.51) |
| `UD-Q3_K_XL`, 8192 | 12,768 MiB | 12,800 (12,300 to 13,500) | yes | 1.09 (0.54) |
| projector, 8192 | 17,025 MiB (1,390 more after a picture) | 1,000 to 1,700 more | yes (1,263) | |

The projector row adds the cortex's vision tail
(`--mmproj mmproj-F16.gguf --image-max-tokens 1024 --ubatch-size 1024`): `/props` reports vision,
and the HARBOUR picture of `test_attached_image_live.py`, sent as a user attachment, was named in 3
of 3 replies (predicted 3, 2 to 3, held). The deep tier has no projector setting; the pick's and the
alternate's projectors, on the mount, were not drawn. At 16384 the pick costs 658 MiB more
(2026-08-04).

**The built-in multi-token-prediction layer**, `--spec-type draft-mtp` with no `--model-draft`.
Both drafting logs print `creating MTP draft context against the target model`, and a plain start
lists `blk.64` as unused. Drawn drafting, plain, drafting, as the pick's drafter was on 2026-09-19:
seed 42, not streamed, a warm-up and three timed requests a turn.

| turn | drafting over plain | accepted | predicted | held | SM (plain; drafting) |
| --- | --- | --- | --- | --- | --- |
| reasoning, `max_tokens` 512 | 1.41, 1.40 | 347 of 490 | 1.6 (1.2 to 2.2) | yes | 0.49; 0.52, 0.53 |
| tool call, `max_tokens` 1024 | 1.43, 1.43 | 70 of 96 | 1.3 (1.0 to 1.7) | yes | 0.54; 0.47, 0.55 |
| answer text, thinking off, `max_tokens` 512 | 1.16, 1.16 | 308 of 604 | 1.3 (1.0 to 1.7) | yes | 0.47; 0.52, 0.53 |

The layer costs 952 and 954 MiB above plain (predicted 470, not held) and loads in 0.99 to 1.12
times plain. Ceilings were 0.87 to 0.89 and the cap active in every busy reading, and no drafting
median fell inside the plain spread. At temperature 1.0 seed 42 repeats one draw within a start, so
each ratio is one text against another, as in the pick's row.

**Injection**, drawn as the tier runs (thinking on, effort unset, the harness's 1600-token cap): 0
of 100 framed (predicted 2, 0 to 8, held) and 0 of 100 control (predicted 15, 5 to 35, not held), so
framed and control are not apart (predicted apart, not held) and framed is not apart from the pick's
0 of 100 (held). The row is in [injection text rows](injection-text-rows.md).

## The stop rows

Each cell is the four questions below, three seeds each (`100*q + d`), sent as the plain security
preamble and the question with no tools and no cap. Deciding count: draws ending on `stop` with a
non-empty `content` before the context fills, of 12, against the pick's count on the same draws by
a two-sided Fisher test at p below 0.05; against the pick's 11 a cell reads apart only at 5 or
fewer. Right by hand is read beside it and decides nothing.

| cell | stopped (predicted) | held | p, against the pick | right | reasoning tokens, median (range) | wall | SM, ceiling |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.8 `xhigh`, nothing sent | 10 (9, 4 to 12) | yes | 1.0 | 10 | 2189 (1032 to 7888) | 1.28 | 0.49, 0.89 |
| the pick | 11 (12, 10 to 12) | yes | | 10 | 1434 (832 to 7923) | 1.0 | 0.57, 0.87 |
| Qwen3.8 `reasoning_effort: "low"` | 12 (12, 10 to 12) | yes | 1.0; 0.48 against `xhigh` | 10 | 1122 (919 to 3892) | 0.78 | 0.47, 0.86 |
| Qwen3.8 `reasoning_effort: "medium"` | 12 (11, 7 to 12) | yes | 1.0; 0.48 | 11 | 1357 (912 to 7004) | 0.97 | 0.49, 0.88 |
| Qwen3.8 `xhigh` and `min_p: 0` | 9 (as `xhigh`, not apart) | yes, p 1.0 | 0.59 | 9 | 2594 (1204 to 7888) | 1.43 | 0.49, 0.88 |
| Qwen3.6-27B, the alternate | 10 (11, 7 to 12) | yes | 1.0 | 9 | 4118 (2280 to 7984) | 2.36 | 0.46, 0.90 |

Every draw that did not stop spent the whole context reasoning (7888 to 7984 tokens) and returned an
empty reply: on Q4, the roster, Qwen3.8 at `xhigh` 2 of 3, with min_p 0 3 of 3, the pick 1 of 3; on
Q2 the alternate 2 of 3. At `low` and `medium` every draw stopped; `low` did not shorten Q2's
reasoning (3269 to 3892 tokens against 1975 to 3978). Replies that returned content ran 384 tokens
at the median at `xhigh`, 546 at `low`, 644 at `medium`, 643 on the pick and 734 on the alternate.
The wrong answers: the pick's Q4 d1, `low`'s Q4 d2 and d3 and the alternate's Q4 d1, each a roster
in which the owner alone covers a shift that needs two people, and `medium`'s Q2 d1 (284/105). Only
Q1 d1 sent an uncached prompt: its first delta came at 0.40 and 0.43 s on Qwen3.8 and 0.48 s on the
pick, and at 2.35 s where it was the first request after a load. The condition for row 4 again at
16384 (row 4 at 7 or fewer) did not fire, and min_p 0, sent because `/props` read 0.05, was
confirmed on `/slots`.

On the alternate a live render of the three leading system messages keeps the preamble and the
memory and drops the recap: its template merges the first two and skips any later one. The
adapter now joins the three for this template, so the recap reaches it
([ADR-0071](../adr/ADR-0071-leading-system-messages.md)). It loaded in 96.8 s (16,417 MiB; 16,443
on 2026-08-04).

## Qwen3.8-Flash-Next: the feasibility row

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
| first chunk of the 3400-word prompt | not drawn | none by the 240 s cut | 120 s: fails | over 240 s | yes |
| VRAM above idle at ready | 20,150 MiB | 20,655 MiB | | | |
| mount read a decoded token, first draw | 65 MB | 119 MB | | | |

The floors, as written: the load passes at both caps. The decode rule named two draws and not which
decides; each run's first draw is under 7.5 and its second, which reused the prompt and the experts
the first had paged in, is over it, so the decode floor is undecided. The first-token floor fails at
20g: 4150 of 6184 prompt tokens were evaluated by 235.8 s, 2048 at a time in 91 to 131 s a step,
which puts the first token near 330 to 370 s (extrapolated). At 24g it was not drawn; the 72-token
prompt both runs evaluated took 61.3 s there and 59.2 s at 20g, so the larger cap did not speed
prompt evaluation. Predicted, memory at the cap with pages read on every token: held. Predicted, the
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

## The four stop-row questions

Each is one user message as written; the answers serve the hand reading only.

**Q1.** Five talks, A, B, C, D and E, fill five one-hour slots starting at 9:00, 10:00, 11:00, 12:00
and 13:00, one talk per slot. B is earlier than D. C is neither first nor last. A comes directly
after E. D is not at 11:00. B does not come directly before C. E is later than C. Give the order of
the talks and show that no other order fits. *Answer: B, D, C, E, A, unique among the 120 orders.*

**Q2.** A drawer holds 4 red, 5 blue and 6 green socks. You take socks out at random, one at a time
and without looking, until two of the socks you hold are the same colour. What is the expected
number of socks you take out? Give the exact fraction. *Answer: 4052/1365, about 2.968.*

**Q3.** The function below should return the average of every run of `window` consecutive values.
What does `moving_average([2, 4, 6, 8, 10], 2)` return, what should it return, and what is the
smallest change that fixes it? The message is the question, a blank line and this block in a
`python` fence. *Answer: it returns [3.0, 6.0, 8.0, 10.0], should return [3.0, 5.0, 7.0, 9.0], and
`i > window` becomes `i >= window`.*

```python
def moving_average(values, window):
    out = []
    total = 0
    for i, v in enumerate(values):
        total += v
        if i > window:
            total -= values[i - window]
        if i >= window - 1:
            out.append(total / window)
    return out
```

**Q4.** A bakery is open Monday to Saturday. Each day it needs one person from 6:00 to 10:00, two
people from 10:00 to 14:00 and one person from 14:00 to 18:00. Two employees can each work at most
five days and at most 40 hours a week, in shifts of any length. The owner works every hour nobody
else covers. What is the fewest hours the owner must work in a week? Give a roster that achieves it.
*Answer: 16, since the week needs 96 person-hours and the employees give at most 80: one works 6:00
to 14:00 Monday to Friday, the other 10:00 to 18:00 Tuesday to Saturday, the owner the rest.*

Method: the drivers in `measurements/deep-2026-09-26/q27-drivers/` (stop rows `phase1.py` to
`phase5.py` over `questions.py`), `flash-p2/` and `flash-p2-20g/` (Flash-Next), the decode probe
`test_decode_cadence_live.py`, the switch probe through `just switch-tail`, and R-714's
`text_rows.py` for the injection row.
