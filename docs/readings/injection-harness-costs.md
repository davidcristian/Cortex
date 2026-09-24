# Readings: what the injection harness's image runs cost

What a corpus screen costs in prompt tokens, how often a draw comes back void, what a row costs in
generated tokens and time, and the card condition those costs were measured under. Cited by
[ADR-0041](../adr/ADR-0041-injection-image-variant.md) (the cost rows, the void limit, the rule that a
price is tokens and a clock, and the card readings). The counts these runs published are in
[injection-over-pixels](injection-over-pixels.md), whose conditions this record shares.

## What one corpus screen costs

Prompt tokens a plain corpus screen adds, read by
`test_what_this_corpus_costs_in_image_tokens_at_each_frame`, which asserts the `FrameAxis` shape.

| candidate | budget | 1600x900 | 3200x1800 | 4800x2700 | shape |
|---|---|---|---|---|---|
| pick, gemma-4-12B | engine | 266 | 266 | 266 | one picture |
| pick | shipped, 1024 | 629 | 1010 | 1010 | more picture |
| alt, Qwen3.5-9B | engine | 1402 | 4082 | 4082 | more picture |
| alt | shipped, 1024 | 1010 | 1010 | 1010 | one picture |

Dates: the pick's two frames 2026-09-04, the third frame 2026-09-07, the alt 2026-09-07; the table
as the row prints it 2026-09-10. The alt uses its whole shipped image budget on a 1600x900 capture,
and it fails both of the pick's saturation assertions.

## Void draws

A void draw returns empty or cut content after thinking to the end of its 16384-token slot.

| date | candidate, budget | void draws | rate |
|---|---|---|---|
| 2026-09-12 | pick, engine, pooled over every row at that budget | 4 in 1200 | 0.33% (0.09 to 0.85) |
| 2026-09-12 | alt, control variants of that run's rows | 15 in 135 | 11.1% |
| 2026-09-12 | alt, framed variants of the same rows | 1 in 135 | 0.74% |
| 2026-09-22 to 09-24 | pick, both budgets, sampler | 0 in 3520 | 0% (0 to 0.10) |
| 2026-09-23, 09-24 | alt, engine, control variants, sampler | 1 in 210 | 0.48% (0.01 to 2.6) |
| 2026-09-23, 09-24 | alt, engine, framed variants, sampler | 1 in 210 | 0.48% (0.01 to 2.6) |
| 2026-09-23 | alt, shipped, `plain` framed, sampler | 3 in 280 | 1.07% (0.22 to 3.1) |

Intervals are exact binomial 95%. The 2026-09-12 rows were drawn at temperature 0 with the prompt
cache on, where a control is one answer per cell: six of the fifteen control voids are one mail
cell's answer, and there the alt's two variants part at p = 0.0004 (Fisher's exact test). At the
engine's sampler they do not: 1 against 1 on the engine budget reads p = 1.0, and the shipped
`plain` row's control half did not finish. Every sampled void ended `'length'`: the control after
11495 generated tokens, the engine-budget framed one after 13819 and the shipped framed three after
14213 to 14215. The rows are in [injection-over-pixels](injection-over-pixels.md#the-alt-candidate),
the 2026-09-23 engine rows in
[R-695](../refinements/tasks/695-an-alt-mail-control-voids-in-every-draw-at-the-engine-budget.md). One pick void draw on
2026-09-07 thought to 15181 tokens in 201.70 s before returning nothing. Method: the void counts
`assert_drawn` prints per reading, summed over the named rows, and for the stopped `plain` row its
printed void lines.

## Generated tokens and time

| date | row | reading |
|---|---|---|
| 2026-09-12 | pick, engine budget, deep row over three renderings | about 6.3 s a reply |
| 2026-09-13 | pick, mail cell at the engine budget, 400 per variant | 2.88 s a request |
| 2026-09-13 | alt, payload-size runs at the shipped budget | about 6.2 s a request |
| 2026-09-13 | alt, third frame at the engine budget | about 13.0 s a request, card clock not read |
| 2026-09-12 | alt, matrices at more frames and budgets | about 14.9 s a request |
| 2026-09-13 | a cold load in a loads row | about 31.8 s |
| 2026-09-10 | alt, chrome laundering control against framed | about 9 times a framed draw's time, 1500 to 1800 reasoning tokens |
| 2026-09-13 | alt, engine-budget series, first two and a half cells | 71854 tokens in 31 replies, at the lowered power limit |
| 2026-09-17 | unattended run, six rows | 1.59 times their full-clock estimates |

In the alt's engine-budget series the control variants drew identical replies of 853, 4050 and 14176
tokens, the last filling the 16383-token context and released as truncated. That spread is why a
row's price is its own generated total and not a per-request figure. Rows drawn the night of
2026-09-12 to 13 ran at the lowered power limit described below, so their figures compare only with
each other.

Method: `Reply.generated` from the server's `usage.completion_tokens`, printed at the end of every
variant's rate line; seconds from the row's own timing lines. Logs on the host under
`measurements/`.

## The engine's sampler rows

The pick's laundering rows at the engine's sampler, whose counts are in [injection over
pixels](injection-over-pixels.md#output-laundering-pick-at-the-engines-sampler). On 2026-09-22, 723
requests a row: 34 min 52 s and 97466 generated tokens at the shipped budget, 55 min 45 s and 196145
at the engine budget, so about 12 and 19 minutes a cell. The framed variant generated 1.75 to 2.57
times the control's tokens at the shipped budget and 1.0 to 1.35 at the engine budget. Under load
the clock was at a median 0.61 of the card's maximum SM clock (0.54 to 0.64) at the shipped budget
and 0.60 (0.57 to 0.67) at the engine budget, the ceiling at 0.80 to 0.88 of its maximum in both
rows, with the software power cap active in 332 of 390 and 559 of 627 serving readings.

| date | row | wall clock and generated tokens | median SM clock of max |
|---|---|---|---|
| 2026-09-23 | mail cell, 400 per variant | 1856 s, 76609 | 0.63 |
| 2026-09-23 | `plain` at 4800x2700, 120 per variant | 1199 s, 68877 | 0.62 |
| 2026-09-24, 01:55 | mail cell, 400 per variant | 1904 s, 73884 | 0.66 |
| 2026-09-24, 01:55 | `plain` at 4800x2700, 120 per variant | 1301 s, 71267 | 0.66 |
| 2026-09-24, 05:38 | mail cell, 400 per variant | 1899 s, 73094 | 0.66 |

Each median is over the row in its run's `clocks.csv`, the ceiling at 0.80 to 0.91 of its maximum.

## The card's power limit

Every figure is a ratio of the card's own numbers, read with `nvidia-smi` (the host binary at
`/usr/lib/wsl/lib/nvidia-smi`, or `docker exec cortex-inj-probe nvidia-smi` from a harness row).
The fields are `enforced.power.limit` against `power.max_limit` and `power.default_limit`,
`power.draw` against `power.max_limit`, and `clocks.sm` against `clocks.max.sm`.

- **2026-09-13, idle, two readings on one day.** After a night with the display asleep: enforced
  limit under a third of max and under three fifths of default, SM clock about half its max, draw
  about a tenth of max. With the desktop awake: limit above nine tenths of max and above default,
  clock a little over half, draw about a fifth. The cause was attributed to display sleep, not
  measured. About six hours had accumulated under each software limit and almost none under a
  hardware one.
- **2026-09-12 and 13, under load, two runs.** SM clock an eighth to a tenth of its max, draw at the
  enforced limit, about a third of max. Every row drawn that night ran at this limit.
- **2026-09-17, idle, six readings in five minutes.** Limit 0.87, 0.83, 0.80, 0.80, 0.80 and 0.88 of
  max, always above default. Through the harness's own card line: limit 0.80 of max and 1.47 of
  default, draw 0.34 of max, SM clock 0.75 to 0.76 of max. Start and end readings therefore do not
  bound a row's limit.
- **2026-09-17 and 19, two unattended runs.** Every row's limit stayed between 0.80 and 0.88 of max;
  clock medians were 0.59 to 0.61 of max for the pick and 0.52 to 0.54 for the alt. The software
  power cap read active in most serving readings while the start and end readings read not active.

## Whether reading the card slows the draw

**2026-09-19.** Qwen3.5-4B, 4096-token draws, three rounds each way. Rounds with the card read every
2 s generated at 1.00, 1.00 and 1.02 times the mean rate of the unsampled rounds, whose own spread
was about 1%. Each `docker exec` took 0.07 to 0.11 s. Limit 0.80 to 0.87 of max, clock 0.56 to 0.60,
cap active in 43 of 45 readings. A live harness draw sampled every 5 s printed 6 readings, limit
0.83 to 0.86, clock 0.58 to 0.61, cap active in 5 of 6 while both end readings read not active.

Method: a probe script on the host (`measurements/serving-sampler-2026-09-19/`) and the harness's
serving line from `card_reading.py`.
