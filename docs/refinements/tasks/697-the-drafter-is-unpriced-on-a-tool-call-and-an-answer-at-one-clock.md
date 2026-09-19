# The deep tier's drafter is unpriced on a tool call and on answer text at one clock

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-19

Opened 2026-09-19 by the landing of the deep tier's drafter setting, which closed
[R-117](117-mtp-model-variants.md) and recorded this step as the one it left.

`CORTEX_MODEL_FILE_BRAIN_DRAFT` now starts the deep model with its multi-token-prediction drafter
(`--model-draft PATH --spec-type draft-mtp`, built by `drafter_flags` in
`brain/packages/model_manager/src/cortex_model_manager/tiers.py`), and it ships empty. Writing a
default there, in `docker/docker-compose.gpu.yml`, or in the runbook's recommendation waits on two
readings the ADR-0004 drafter addendum of 2026-09-17 does not have:

1. **The tool-call turn at one clock.** That addendum's second pair ran the drafter at 1.37 times
   the plain median on one `search_email` turn, but the drafter arm decoded at 0.45 of
   `clocks.max.sm` and the plain arm at 0.62, outside the tenth its pre-registered rule allows, so
   the pair does not decide. Repeat it with the same rule, one warm-up and three timed requests per
   arm, and publish each arm's clock and ceiling from the serving-line readings. If the card's
   throttle keeps the two arms apart, alternate the arms (drafter, plain, drafter) so a drift shows
   as a gap between the two drafter arms rather than as a speed-up.
2. **One answer-text turn beside it.** All 512 tokens of the first pair's prompt fell inside the
   reasoning trace, so acceptance on the reply itself is unmeasured. Price one turn whose reply
   carries text (a reasoning budget on the deep tier, or a prompt that ends its trace early) under
   the same rule, reading `timings.draft_n` and `timings.draft_n_accepted` beside the decode rate.

The rule to write first: the drafter earns a default when both turns clear the plain arm's spread
at matched clocks. A null on either leaves the setting opt-in, which is what ships.

## The 2026-09-19 sitting, registered before its first start

Written before any start ran, and left unchanged after the results.

- **Starts, in order:** drafter, plain, drafter, each a fresh container of the cached
  `ghcr.io/ggml-org/llama.cpp:server-cuda` (`952424b09abc`) running the deep tier's argv as
  `ModelHostConfig.tiers()` builds it (`-ngl 99 --ctx-size 8192 --parallel 1 --jinja --cache-ram 0`),
  the drafter starts adding `drafter_flags` for `google/gemma-4-31B-it-assistant/assistant-F16.gguf`.
  Each container is removed and the card left idle for 30 s before the next start, which then
  spends its load with the card near idle.
- **Turns per start, in order:** the tool-call turn (one `search_email` tool, `max_tokens` 1024),
  then the answer-text turn (a prose request with `chat_template_kwargs: {"enable_thinking": false}`,
  the brain's own no-reasoning shape, `max_tokens` 512). Each turn is one warm-up and three timed
  requests of one prompt, seed 42, the server's default sampling.
- **Readings:** `timings.predicted_per_second`, `draft_n` and `draft_n_accepted` per request;
  `nvidia-smi` every 2 s through each start. A turn's clock is the median `clocks.sm` over samples
  inside its three timed requests with `utilization.gpu` at 50 or more, as a fraction of
  `clocks.max.sm`; its ceiling is the same samples' `enforced.power.limit` over `power.max_limit`.
- **Deciding comparison, per turn:** a drafter start clears when its median decode rate exceeds the
  plain start's median by more than the plain start's spread (highest minus lowest of its three).
  Only a drafter start whose turn clock is within 0.10 of the plain start's counts. The turn is
  met when at least one drafter start counts and every counting start clears; failed when a
  counting start does not clear.
- **Null:** a turn with no counting drafter start (the clock clause failed for both), or whose
  timed replies do not all have the turn's shape (every tool-call reply ends in a tool call; every
  answer-text reply carries content and no reasoning), is null. A gap between the two drafter
  starts' clocks larger than 0.10 is reported as drift.
- **Decision:** the default is written only when both turns are met and at least 20 minutes of
  the slot remain; otherwise the setting stays opt-in and this entry stays open.
- **Log:** `measurements/mtp-2026-09-19/` on the host, one log, JSON and sampler CSV per start.

## What the sitting read, and the next step

The tool-call turn was met: both drafter starts decoded 1.32 and 1.33 times the plain median,
against a plain spread of 0.02 of it, at clocks 0.095 and 0.092 below the plain start's. The
answer-text turn was null on the clock clause alone: the drafter starts ran 1.34 and 1.35 times
the plain median against a spread of 0.01, every reply carried text and no trace, and their clocks
sat 0.101 and 0.109 below the plain start's. The gap is not drift (the two drafter starts differ in
clock by 0.008), and in all seven drafter-to-plain comparisons of this sitting and the 2026-09-17
one the drafter ran the lower clock, by 0.09 to 0.17. In this sitting the power cap was active in
65 of 66 busy samples across all three starts. The figures are in the ADR-0004 drafter addendum's
section on this sitting.

So the rule's matched-clock clause, as written, compares something the drafter itself changes.
The next card slot registers a rule that matches ceilings instead: a pair counts when both arms'
serving ceilings (`enforced.power.limit` over `power.max_limit`, busy samples) overlap and the
software power cap is active in most busy samples of both, with the drafter, plain, drafter order
and a drafter-to-drafter clock gap within 0.10 as the drift guard, and each arm's clock published
beside its rate. It then draws a fresh sitting of the same two turns with
`measurements/mtp-2026-09-19/arm.py`, changing only the clause in `analyze.py` beside it. Both
turns met writes the default: the drafter's path for `CORTEX_MODEL_FILE_BRAIN_DRAFT` in
`docker/docker-compose.gpu.yml`, with `CORTEX_SWAP_BRAIN_VRAM_MIB` raised by the drafter's cost and
the GPU subagent tier listed in `CORTEX_SWAP_EVICT_MODELS`, as the model-swap runbook says.
Pinning the SM clock for every arm (`nvidia-smi --lock-gpu-clocks`) would keep the clock clause,
but needs administrator rights on the Windows host and is untried.

## Trail

- 2026-09-19: filed from the drafter landing. The engine, the artifacts and the argv are unchanged
  from R-117's reading: the cached `ghcr.io/ggml-org/llama.cpp:server-cuda` (`952424b09abc`, build
  10680) and `google/gemma-4-31B-it-assistant/assistant-F16.gguf` on the mount.
- 2026-09-19: the registered sitting ran. The tool-call turn was met and the answer-text turn was
  null on its clock clause, so no default was written and the setting stays opt-in; the next step
  above replaces that clause with a ceiling match. Logs, sampler files, JSON and both scripts are
  in `measurements/mtp-2026-09-19/` on the host.
