# MTP (multi-token-prediction) model variants

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** an MTP or draft artifact for a shipped tier that this build of llama.cpp loads at all, since no argv, compose file or env in this tree can name one today.

Deferred until they earn their keep, per
[ADR-0004](../../adr/ADR-0004-model-lineup.md).

## Trail

- 2026-08-16: Priced against the tree and given a trigger. The origin is two lines, and both of
  them read differently now than when they were written. **The stated reason has been measured and
  it is survivable on the tier that would want this.** "They use more memory" is a fact about
  artifacts, and the card has the room on the deep tier: gemma-4-31B alone reads 20671 to 20723
  MiB, a 2878 MiB peer beside it reads 23555 to 23642 MiB with about 908 MiB free, and the deep
  model's decode is unharmed at 28.92 to 29.82 tok/s against 25.07 to 33.28 alone. It is fatal
  only for the cortex-plus-deep pairing, which wants 29139 MiB against 24463 and pays for the
  overcommit in decode. **The stated condition has arguably already arrived**, since a deep turn
  spends 3800 to 4500 tokens at about 31 tok/s, which is roughly two minutes of generation on top
  of a 99.6 s load, so decode is the larger half of what a user waits for on that tier and "revisit
  only if latency demands it" no longer names anything that has not happened.
- 2026-08-16: What actually blocks it is neither of those, which is why the trigger is
  upstream-shaped. Nothing in this tree can name such an artifact or hand it to a server: the whole
  repo holds no `--model-draft`, no draft or speculative flag of any spelling, and no MTP filename.
  `llama_server_argv` builds a fixed flag tuple plus a per-tier `extra`
  ([tiers.py](../../../brain/packages/model_manager/src/cortex_model_manager/tiers.py)) whose only
  producers are the thinking-off pair and the vision tail
  ([config.py](../../../brain/packages/model_manager/src/cortex_model_manager/config.py)), with no
  env hook for a free-form argument, and the roster is fixed at boot on purpose, since a
  request-supplied argv would be remote code execution against the GPU container
  ([spec.py](../../../brain/packages/model_manager/src/cortex_model_manager/spec.py)). So this is a
  typed field on `TierArgs`, a second artifact path per tier and a VRAM budget row, not a knob, and
  none of it is worth writing before an artifact exists that the pinned server accepts.
