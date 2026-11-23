# Readings: deep candidates

The rows the deep candidates of [ADR-0004](../adr/ADR-0004-model-lineup.md) (decisions 5, 8 and 14)
are compared on, for the two Qwen3.8 candidates, with gemma-4-31B and Qwen3.6-27B redrawn beside them.
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
0.0), and 1.0, 64, 0.95 and 0.05 on gemma-4-31B. A row that departs names the field it adds. gemma-4-31B,
`gemma-4-31B-it-qat-q4_0`, runs with no drafter, as it ships. Every load ran at an SM clock of 0.59,
reading the models mount. Logs and drivers: `measurements/deep-2026-09-26/`, which git ignores.

## The candidates side by side

Ratios are of gemma-4-31B's own figure unless a bound is named.

| reading | gemma-4-31B | Qwen3.8-27B UD-Q4_K_M | Qwen3.6-27B Q4_K_M | Qwen3.8-Flash-Next UD-Q3_K_XL |
| --- | --- | --- | --- | --- |
| artifact | 17.65 GB, QAT | 16.46 GB | 16.82 GB | 89.98 GB in three files |
| VRAM above idle, 8192 context | 19,138 MiB | 15,744 to 15,770 MiB | 16,417 MiB | 20,150 to 20,655 MiB, the rest paged from the mount |
| ready, of the 300 s load bound | 0.32 | 0.29 the first time, 0.20 to 0.22 after | 0.32 | 0.45 to 0.69 |
| stop row: stopped, right by hand, of 12 | 11, 10 | 10, 10 at `xhigh`; 12, 10 at `low`; 12, 11 at `medium` | 10, 9 | not drawn |
| reasoning tokens a stop-row draw, median | 1434 | 2189 `xhigh`, 1122 `low`, 1357 `medium` | 4118 | not drawn |
| stop-row wall a draw, median | 1.0 | 1.28 `xhigh`, 0.78 `low`, 0.97 `medium` | 2.36 | not drawn |
| decode | 1.0 | 1.01, at SM 0.50 against 0.59 | 1.02 on the stop draws, at SM 0.46 against 0.57 | 0.09 to 0.14 over 128 tokens, 0.23 over 2000 at SM 0.69 |
| first chunk of the 3400-word prompt, of the 120 s stall bound | 0.037 (4018 tokens) | 0.040 (6184 tokens) | not drawn | 1.65 at the shipped 24g cap; none within twice the bound at 20g |
| injection, framed and control obeyed of 100 | 0 and 8 (2026-09-24) | 0 and 0; 0 and 0 as the tier starts at 16384, drafting or not (2026-11-21) | not drawn | not drawn |
| multi-token prediction | a separate drafter file, 1.34 to 1.89 times plain | a built-in layer, 1.16 to 1.43 times plain, which no setting names | not drawn | none in the artifact |
| template | | `xhigh` unless sent; empty thoughts before earlier replies | drops a third leading system message, which the adapter now joins ([ADR-0071](../adr/ADR-0071-leading-system-messages.md)) | the 27B's, byte for byte |

gemma-4-31B's stop-row draw took 58 s at the median and its decode probe read 37.15 tok/s
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

**Rates**, each the median of 3, gemma-4-31B drawn 25 minutes later:

| reading | Qwen3.8-27B over gemma-4-31B | predicted | held | SM, ceiling (Qwen; gemma-4-31B) |
| --- | --- | --- | --- | --- |
| decode probe (`test_decode_cadence_live.py`, thinking on) | 1.01 | 1.0 (0.9 to 1.15) | yes | 0.50, 0.89; 0.59, 0.90 |
| first streamed delta, 3400-word prompt, `max_tokens` 16 | 1.09 | 0.8 to 1.3 | yes | as above |
| share of round 2's prompt evaluated, two-round tool loop | 0.16 (pick 0.23) | 0.9 to 1.0 | no | as above |

The decode probe asks for about 120 words: Qwen3.8 generated 1545 to 2063 tokens, gemma-4-31B 409 to
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
of 3 replies (predicted 3, 2 to 3, held). The deep tier has no projector setting; gemma-4-31B's and
Qwen3.6-27B's projectors, on the mount, were not drawn. At 16384 gemma-4-31B costs 658 MiB more
(2026-08-04).

**The built-in multi-token-prediction layer**, `--spec-type draft-mtp` with no `--model-draft`.
Both drafting logs print `creating MTP draft context against the target model`, and a plain start
lists `blk.64` as unused. Drawn drafting, plain, drafting, as gemma-4-31B's drafter was on 2026-09-19:
seed 42, not streamed, a warm-up and three timed requests a turn.

| turn | drafting over plain | accepted | predicted | held | SM (plain; drafting) |
| --- | --- | --- | --- | --- | --- |
| reasoning, `max_tokens` 512 | 1.41, 1.40 | 347 of 490 | 1.6 (1.2 to 2.2) | yes | 0.49; 0.52, 0.53 |
| tool call, `max_tokens` 1024 | 1.43, 1.43 | 70 of 96 | 1.3 (1.0 to 1.7) | yes | 0.54; 0.47, 0.55 |
| answer text, thinking off, `max_tokens` 512 | 1.16, 1.16 | 308 of 604 | 1.3 (1.0 to 1.7) | yes | 0.47; 0.52, 0.53 |

The layer costs 952 and 954 MiB above plain (predicted 470, not held) and loads in 0.99 to 1.12
times plain. Ceilings were 0.87 to 0.89 and the cap active in every busy reading, and no drafting
median fell inside the plain spread. At temperature 1.0 seed 42 repeats one draw within a start, so
each ratio is one text against another, as in gemma-4-31B's row.

**Injection**, drawn as the tier runs (thinking on, effort unset, the harness's 1600-token cap): 0
of 100 framed (predicted 2, 0 to 8, held) and 0 of 100 control (predicted 15, 5 to 35, not held), so
framed and control are not apart (predicted apart, not held) and framed is not apart from gemma-4-31B's
0 of 100 (held); at the shipped 16384 on 2026-11-21, 0 and 0 ([rows](injection-text-rows.md)).

## The stop rows

Each cell is the four questions below, three seeds each (`100*q + d`), sent as the plain security
preamble and the question with no tools and no cap. Deciding count: draws ending on `stop` with a
non-empty `content` before the context fills, of 12, against gemma-4-31B's count on the same draws by
a two-sided Fisher test at p below 0.05; against gemma-4-31B's 11 a cell reads apart only at 5 or
fewer. Right by hand is read beside it and decides nothing.

| cell | stopped (predicted) | held | p, against gemma-4-31B | right | reasoning tokens, median (range) | wall | SM, ceiling |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.8 `xhigh`, nothing sent | 10 (9, 4 to 12) | yes | 1.0 | 10 | 2189 (1032 to 7888) | 1.28 | 0.49, 0.89 |
| gemma-4-31B | 11 (12, 10 to 12) | yes | | 10 | 1434 (832 to 7923) | 1.0 | 0.57, 0.87 |
| Qwen3.8 `reasoning_effort: "low"` | 12 (12, 10 to 12) | yes | 1.0; 0.48 against `xhigh` | 10 | 1122 (919 to 3892) | 0.78 | 0.47, 0.86 |
| Qwen3.8 `reasoning_effort: "medium"` | 12 (11, 7 to 12) | yes | 1.0; 0.48 | 11 | 1357 (912 to 7004) | 0.97 | 0.49, 0.88 |
| Qwen3.8 `xhigh` and `min_p: 0` | 9 (as `xhigh`, not apart) | yes, p 1.0 | 0.59 | 9 | 2594 (1204 to 7888) | 1.43 | 0.49, 0.88 |
| Qwen3.6-27B | 10 (11, 7 to 12) | yes | 1.0 | 9 | 4118 (2280 to 7984) | 2.36 | 0.46, 0.90 |
| gemma-4-31B at a 16384 context, [2026-09-30](history-window.md#the-deep-tier-at-16384) | 12 (12, 10 to 12) | yes | 1.0 | 11 | 1434 (832 to 8341) | 1.20, mostly that night's [decode rate](history-window.md#decode-at-16384-in-one-session) | 0.58, 0.85 |

Every draw that did not stop spent the whole context reasoning (7888 to 7984 tokens) and returned an
empty reply: on Q4, the roster, Qwen3.8 at `xhigh` 2 of 3, with min_p 0 3 of 3, gemma-4-31B 1 of 3; on
Q2 Qwen3.6-27B 2 of 3. At `low` and `medium` every draw stopped; `low` did not shorten Q2's
reasoning (3269 to 3892 tokens against 1975 to 3978). Replies that returned content ran 384 tokens
at the median at `xhigh`, 546 at `low`, 644 at `medium`, 643 on gemma-4-31B and 734 on Qwen3.6-27B.
The wrong answers: gemma-4-31B's Q4 d1, `low`'s Q4 d2 and d3 and Qwen3.6-27B's Q4 d1, each a roster
in which the owner alone covers a shift that needs two people, and `medium`'s Q2 d1 (284/105). Only
Q1 d1 sent an uncached prompt: its first delta came at 0.40 and 0.43 s on Qwen3.8 and 0.48 s on the
pick, and at 2.35 s where it was the first request after a load. The condition for row 4 again at
16384 (row 4 at 7 or fewer) did not fire, and min_p 0, sent because `/props` read 0.05, was
confirmed on `/slots`.

On Qwen3.6-27B a live render of the three leading system messages keeps the preamble and the
memory and drops the recap: its template merges the first two and skips any later one. The
adapter now joins the three for this template, so the recap reaches it
([ADR-0071](../adr/ADR-0071-leading-system-messages.md)). It loaded in 96.8 s (16,417 MiB; 16,443
on 2026-08-04).

## The stop rows at 16384

**2026-11-21**, the pick's file alone on the 24 GB card, engine build `b12375-9d25e0014` from the
`cortex-model-host` image. Only the model host of the repo's compose files was started, with
`CORTEX_MODEL_FILE_BRAIN` naming the file and every other setting on its compose default; the
cortex was stopped and the deep tier started over the control API. The drafted launches also named
the file as `CORTEX_MODEL_FILE_BRAIN_DRAFT`. Every deep server ran `-ngl 99 --ctx-size 16384
--parallel 1 --jinja --cache-ram 0 --cache-type-k q8_0 --cache-type-v q8_0`, the drafted ones with
`--spec-type draft-mtp --spec-draft-n-max 3` and both draft cache flags at `q8_0`. The draws are
the cells' above, with the same request, no cap and the sampler of 2026-09-26; `medium` and `low`
are the request field `reasoning_effort`. The predictions were written into
[R-1266](../refinements/tasks/1266-qwen38-27b-has-no-stop-row-at-the-shipped-16384-context.md)
before the first draw. Against gemma-4-31B's 12 of 12 a cell reads apart only at 7 or fewer.

| cell | stopped (predicted) | held | right | reasoning tokens, median (range) (predicted) | held | longest draw, generated | card above the floor, highest |
| --- | --- | --- | --- | --- | --- | --- | --- |
| draft layer, `xhigh`, nothing sent | 12 (11, 9 to 12) | yes | 11 | 2883.5 (831 to 14,964) (2200, 1700 to 3000) | yes | 15,610 | 17,002 MiB |
| no drafter, `xhigh`, nothing sent | 11 (11, 9 to 12) | yes | 10 | 2327 (1014 to 16,080) (2200, 1700 to 3000) | yes | 16,080 | 15,977 MiB |
| no drafter, `medium` | 12 (12, 11 to 12) | yes | 11 | 1182.5 (746 to 9670) (1350, 1000 to 1900) | yes | 10,207 | 15,976 MiB |
| draft layer, `low` | 12 (12, 11 to 12) | yes | 12 | 1415.5 (929 to 6380) (1100, 800 to 1600) | yes | 7086 | 17,004 MiB |
| draft layer, `medium`, 5 of its draws on a later launch ([effort level](deep-effort.md#the-drafted-medium-stop-cell)) | 12 (12, 11 to 12) | yes | 12 | 2378 (976 to 4232) (1350, 1000 to 1900) | no | 5123 | 17,003 MiB |
| no drafter, `low` | not drawn | | | | | | |

- **The one miss.** Q4 d1 at `xhigh` without the drafter reasoned 16,080 tokens, with its 304
  prompt tokens the whole context, and returned no reply. Three more Q4 draws stopped late: after
  14,964 reasoning tokens with the layer at `xhigh`, 470 tokens before the context's end, after
  10,458 without it, and after 9670 at `medium`. Each would have filled the first rows' 8192. No
  Q1 to Q3 draw generated more than 6799 tokens, as predicted.
- **A handoff's room.** 5 of the 24 `xhigh` draws, 1 undrafted draw of the 24 at `medium` and 1 of
  the 12 `low` draws generated more than the 5521 tokens a full history window leaves at 16384.
  [Behind a full handoff prompt](deep-handoff-room.md) both drafted cells stopped on 11 of 12.
- **The effort field.** `POST /apply-template` on the deep server renders the `xhigh` sentence
  when nothing, `high` or `xhigh` is sent, a `low` sentence at `low` and no effort sentence at
  `medium`: 322, 310 and 284 prompt tokens on Q3, which a completion's `usage.prompt_tokens`
  matched. `chat_template_kwargs` naming the effort renders the same bytes as the field.
- **The drafter.** 12 against 11 at `xhigh` is the predicted null result. No drafted reply has
  the undrafted reply's text. The drafted `xhigh` cell decoded at 1.98 times the undrafted cell's
  median rate, with 32,347 of 56,589 drafted tokens accepted.
- **Right by hand.** Wrong: Q4 d1 with the layer at `xhigh` (the owner alone on a Saturday that
  needs two people for four hours), Q2 d1 without it (3764/1365) and Q2 d1 at `medium` (284/105).

Method: `up.sh`, `stop16.py` and `effort_probe.py` in `~/.cache/cortex-run/2026-11-21/s1/` over the
first rows' `questions.py`; `cells/` there has every reply and `grades.md` the hand reading.

## Qwen3.8-Flash-Next

Its feasibility rows, at the shipped 24g cap and at a 20g cap, are in
[Qwen3.8-Flash-Next](flash-next.md).

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
`phase5.py` over `questions.py`), the decode probe `test_decode_cadence_live.py`, the switch
probe through `just switch-tail`, and R-714's `text_rows.py` for the injection row.
