# MTP (multi-token-prediction) model variants

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** an MTP or draft artifact on the mount for the file a shipped tier is actually started on, which is a narrower set than the candidates the lineup names at that tier, together with a start of the pinned engine on that file that loads.

Deferred until the latency they save justifies the memory they cost, per
[ADR-0004](../../adr/ADR-0004-model-lineup.md).

## Trail

- 2026-08-16: Priced against the tree and given a trigger. The origin is two lines, and both of
  them read differently now than when they were written. **The stated reason has been measured and
  it is survivable on the tier that would want this.** "They use more memory" is a fact about
  artifacts, and the card has the room on the deep tier: gemma-4-31B alone reads 20671 to 20723
  MiB, a 2878 MiB peer beside it reads 23555 to 23642 MiB with about 908 MiB free, and the deep
  model's decode is unharmed at 28.92 to 29.82 tok/s against 25.07 to 33.28 alone. It is fatal
  only for the cortex-plus-deep pairing, which needs 29139 MiB against 24463 and pays for the
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
- 2026-09-06: Checked against the mount and the pinned engine, and not fired. Six MTP artifacts
  are on the mount: `unsloth/Qwen3.5-9B-MTP-GGUF/`, `unsloth/Qwen3.6-27B-MTP-GGUF/` and
  `unsloth/Qwen3.6-35B-A3B-MTP-GGUF/`, plus three `llmfan46/...-Native-MTP-Preserved-GGUF/`
  directories. Each is a same-file variant rather than a separate draft model, which the sizes say:
  the MTP `Qwen3.5-9B-UD-Q4_K_XL.gguf` is 6135034208 bytes against 5966095584 for its non-MTP twin
  in `unsloth/Qwen3.5-9B-GGUF/`, so the extra tensors ride inside the one artifact. **None of them
  is a shipped pick.** The cortex tier starts on `google/gemma-4-12B-it-qat-q4_0-gguf/...`
  ([docker-compose.gpu.yml](../../../docker/docker-compose.gpu.yml)) and the subagent tier on
  `google/gemma-4-E4B-it-qat-q4_0-gguf/...`
  ([docker-compose.subagents.yml](../../../docker/docker-compose.subagents.yml)); the mount holds no
  gemma MTP artifact at all. Qwen3.5-9B is a cortex **candidate** in the lineup above and
  Qwen3.6-27B and Qwen3.6-35B-A3B are brain candidates, and the deep pick is still open, so the
  three Qwen MTP directories name candidates rather than picks. That gap between candidate and pick
  is why the trigger now says which of the two it means.
- 2026-09-06: **The engine half of the deferral has expired, and the tree half has not.** The
  entry above says the block is upstream-shaped, that nothing here can name such an artifact and no
  build here would take one. The second of those is no longer true. Both cached tags now report
  `version: 0.3.0-dev (build 10680, commit d7bd3bfca)`, and that build advertises a full
  speculative family: `--spec-draft-model, -md, --model-draft FNAME`, alongside `--spec-draft-hf`,
  `--spec-draft-threads`, `--spec-draft-cpu-mask`, `--spec-draft-type-k`, `--spec-draft-type-v` and
  `--spec-draft-override-tensor`. So the flag to hand a draft artifact to a server exists in the
  image the stack runs. What still holds is the tree: a grep for `model-draft`, `spec-draft`,
  `--draft` and `speculative` across every `.py`, `.yml`, `.rs` and `.toml` here returns one
  sentence in a fake saying there are no speculative knobs, and nothing else. The typed field on
  `TierArgs`, the second artifact path per tier and the VRAM budget row are still the work, and the
  reason to wait is now the pick rather than the engine.
