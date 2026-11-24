# The roster alternate hands back the report less often at its card's sampler

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-24

Qwen3.5-2B, the file the roster alternate `llama-subagent-qwen` serves, runs the engine's sampler.
On the envelope's every-detail summary it hands the report body back in 12 to 20 runs of 32 at that
sampler, and in 0 to 2 at its card's thinking-off values (temperature 1.0, `top_p` 1.0, `top_k` 20,
`min_p` 0, presence penalty 2.0). It delivers 28 or 29 of 32 at the card's values against 10 to 20,
on the card and on the roster server's own image and argv
([card samplers](../../readings/card-samplers.md#the-every-detail-shape-drawn-again)).

Over the four shapes of the first row the two samplers were not told apart, 85 against 94 of 128:
the extraction and the lookup delivered 4 and 5 runs fewer at the card's values. The injection row
read 14 against 10 framed obeyed of 100. The rule written before that row ships a sampler only on a
difference over all four shapes, so the roster server kept the engine's sampler.

What would close it: a rule written here before the row, then the row on the shipped roster server
(`ghcr.io/ggml-org/llama.cpp:server` on the CPU with the compose argv): the four shapes at a new seed
base, 32 runs a shape, and the injection text row, in three cells. E is the engine's sampler, C the
card's five values, and P the presence penalty of 2.0 alone, which separates the penalty from the
other four values. The proposed rule: a cell ships as flags on `llama-subagent-qwen` in
`docker-compose.subagents-roster.yml` when its delivered count over the 128 runs is higher than E's
at a two-sided Fisher p below 0.05 and its framed obeyed count is not higher at p below 0.05. When C
and P both pass, P ships, since it changes one value.

## History

- 2026-11-24: filed from the rows of
  [R-1240](1240-some-tiers-run-settings-their-model-cards-do-not-recommend.md), when the
  every-detail shape read apart alone and held on new seeds on both placements.
