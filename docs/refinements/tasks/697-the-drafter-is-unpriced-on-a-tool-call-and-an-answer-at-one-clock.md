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

## Trail

- 2026-09-19: filed from the drafter landing. The engine, the artifacts and the argv are unchanged
  from R-117's reading: the cached `ghcr.io/ggml-org/llama.cpp:server-cuda` (`952424b09abc`, build
  10680) and `google/gemma-4-31B-it-assistant/assistant-F16.gguf` on the mount.
