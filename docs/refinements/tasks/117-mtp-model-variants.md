# MTP (multi-token-prediction) model variants

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-17

Deferred until the latency they save justifies the memory they cost, per
[ADR-0004](../../adr/ADR-0004-model-lineup.md).

**Why this is actionable now.** The deep tier's file is fixed: the ADR-0004 brain-pick addendum of
2026-08-04 chose `google/gemma-4-31B-it-qat-q4_0-gguf/gemma-4-31B_q4_0-it.gguf`. The mount holds
its MTP drafter, `google/gemma-4-31B-it-assistant/assistant-F16.gguf` (954843360 bytes,
`general.architecture` `gemma4-assistant`), and the 2026-09-17 sitting below measured that the
pinned engine loads the pair and that the drafter pays: decode ran at 1.86 to 1.89 times the plain
rate for about 1000 MiB more on the card. So the build is what remains.

**Pre-registered for the 2026-09-17 sitting**, written before any arm ran. Engine: the cached
`ghcr.io/ggml-org/llama.cpp:server-cuda` (`952424b09abc`, build 10680), whose `--help` offers the
drafter as `--model-draft FNAME` with `--spec-type draft-mtp` or `draft-simple`; a bare `--mtp` is
rejected as an invalid argument. Both arms start the deep tier's shipped argv from
`ModelHostConfig.tiers()`: `-ngl 99 --ctx-size 8192 --parallel 1 --jinja --cache-ram 0`, no
reasoning budget. Arm A adds nothing; arm B adds the drafter with `--spec-type draft-mtp`, and
`draft-simple` is tried only if that fails to load. Each arm sends one untimed warm-up and then four
timed requests of one fixed prompt to `/v1/chat/completions` with `max_tokens` 512 and seed 42 and
no sampling fields, since the brain sends none. The reading per request is the server's
`timings.predicted_per_second`; `nvidia-smi` is sampled every two seconds through each arm.
**Deciding comparison:** the drafter pays when arm B's median decode rate exceeds arm A's by more
than arm A's spread (fastest minus slowest of its four), with the decode clock of both arms within
a tenth of each other as a fraction of `clocks.max.sm`. **A null** is any other outcome: B no
faster than that, B slower, or a load that fails with both spellings. A null closes this entry as
declined; a win leaves it open with the build specified. A second pair, registered after the
first reading and before it ran, repeats both arms on one tool-call turn (one `tools` entry,
`max_tokens` 1024, one warm-up and three timed requests) under the same rule, and records whether
each reply ends in a tool call.

**The reading** (ADR-0004's 2026-09-17 drafter addendum has the table; the run logs are under
`measurements/mtp-2026-09-17/` on the host). Four starts ran in the order MTP, plain, MTP, and
the draft path with no `--spec-type`. The rule is met by a wide margin: the two MTP arms' medians
sit 0.86 and 0.89 of the plain median above it, against a plain spread of 0.02 of that median. The
drafter accepted 328 of 548 drafted tokens (0.60, mean accepted length 2.79) on every timed
request. Both MTP arms decoded at 0.48 of the maximum clock and the plain arm at 0.57, within the
tenth the rule allows, and the lower clock is the drafter's. `draft-simple` was not needed. The
draft path alone logs loading the drafter and then drafts nothing: no acceptance line, the plain
arm's rate, and used memory within 60 MiB of the plain arm. The reading covers one prompt whose
512 tokens all fell inside the reasoning trace, so acceptance on answer text is unmeasured.

The tool-call pair ran next, drafter first. Every reply in both arms ended in the same
`search_email` call, after 86 tokens with the drafter and 69 without. The drafter's median was
1.37 times the plain median against a plain spread of 0.01 of it, at an acceptance of 46 of 123
(0.37, mean length 2.12). **The pair does not decide, because the clock clause failed:** the
drafter arm decoded at 0.45 of the maximum clock and the plain arm at 0.62, four busy samples each.
The gap runs against the drafter, as in the first pair, but the rule written beforehand does not
count it.

**The build, which is the next landing:**

1. A typed drafter on `TierArgs` (the artifact path and the speculative type as one optional
   value), and `llama_server_argv` writing `--model-draft PATH --spec-type draft-mtp` together
   whenever it is set, since the path alone was measured to draft nothing.
2. `ModelHostConfig` reads the deep tier's drafter from `CORTEX_MODEL_FILE_BRAIN_DRAFT`, empty by
   default so a deployment that names none starts the argv it does today. The name follows the
   `CORTEX_MODEL_FILE_` convention `scripts/artifactnames.py` reads, and `scripts/settingscheck.py`
   will fail until `docker/docker-compose.gpu.yml` hands the field to the model host, so the
   compose line is part of the same change.
3. The VRAM budget: `CORTEX_SWAP_BRAIN_VRAM_MIB`'s comment in `docker/docker-compose.gpu.yml`
   gains the drafter's 997 to 1020 MiB. Added to the 23555 to 23642 MiB the deep model and the
   E4B subagent tier read together, that is more than the card's 24463 MiB (arithmetic, not
   measured), so a deployment turning the drafter on also lists the GPU subagent tier in
   `CORTEX_SWAP_EVICT_MODELS`; the runbook and the compose comment say so.
4. Before a default is written anywhere, the tool-call turn is priced again with the two arms'
   clocks within the rule's tenth, since the pair above missed that clause, and one turn with
   answer text is priced beside it.

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
- 2026-09-11: read against the mount, the cached engine and the tree, and not fired. The mount
  holds the same six MTP directories as on 2026-09-06, the three under `unsloth/` and the three
  under `llmfan46/`, and no MTP or draft artifact under `google/`, whose seven directories hold
  the QAT files of the 12B, 26B-A4B, 31B, E2B and E4B and two `-assistant` variants. The two
  MTP and non-MTP `Qwen3.5-9B-UD-Q4_K_XL.gguf` files still read 6135034208 and 5966095584
  bytes. Both shipped picks are unchanged in their compose files and present on the mount, the
  cortex file at 6975879296 bytes and the subagent file at 5154941280. Both cached tags,
  `:server` at `db057ec90de0` and `:server-cuda` at `952424b09abc`, still report build 10680 at
  commit `d7bd3bfca`, and `:server`'s `--help` still lists `--spec-draft-model, -md,
  --model-draft FNAME`. The grep for `model-draft`, `spec-draft`, `--draft` and `speculative`
  over every `.py`, `.yml`, `.rs` and `.toml` still returns the one sentence in
  `fakes_model_host.py`, and `ModelHostConfig.tiers()` still fills `TierArgs.extra` from
  `_vision()` and `_reasoning()` alone.
- 2026-09-17: **the first half of the trigger had fired before it was written, and two earlier
  readings here were wrong about the mount.** The trigger asked for an MTP or draft artifact for
  the file a shipped tier is started on. `google/gemma-4-31B-it-assistant/` and
  `google/gemma-4-26B-A4B-it-assistant/` have been on the mount since 2026-08-16. Each
  `config.json` names `Gemma4AssistantForCausalLM`, with a `backbone_hidden_size` of 5376 for the
  31B one and 2816 for the 26B-A4B one, their model card calls them the MTP drafters for Gemma 4, and each holds an `assistant-F16.gguf`
  whose header reads `gemma4-assistant`. So the 2026-09-06 reading "the mount holds no gemma MTP
  artifact at all" and the 2026-09-11 reading "no MTP or draft artifact under `google/`" were
  both false. The 2026-09-06 reading "the deep pick is still open" was also false: the deep pick
  was made on 2026-08-04 and is the 31B the first drafter serves. The engine half was read
  without starting anything, by extracting `/app` from a `docker create` of the cached `:server`
  tag (still `db057ec90de0`, and `:server-cuda` still `952424b09abc`): `libllama.so.0.3.0` holds
  `llama_model_gemma4_assistant` and `/app/src/models/gemma4-assistant.cpp`, and
  `libllama-common.so.0.3.0` spells `--model-draft`, `--spec-type`, `--draft-max`, `--gpu-layers-draft`
  and the message `creating MTP draft context against the target model`. No start was made,
  because a GPU sitting held the card, so whether the pair loads is unmeasured. The two shipped
  resident tiers still have no drafter: nothing on the mount serves `gemma-4-12b-it-qat-q4_0.gguf`
  (6975879296 bytes) or `gemma-4-E4B_q4_0-it.gguf` (5154941280 bytes). The tree still spells no
  draft flag: the grep for `model-draft`, `spec-draft`, `--draft` and `speculative` returns the
  one sentence in `fakes_model_host.py`. Re-filed actionable, with the load reading as the next
  step.
- 2026-09-17: the load and decode reading was taken with the card to itself, and it pays. The
  pair loads on build 10680 with `--model-draft` plus `--spec-type draft-mtp`, and decode ran at
  1.86 and 1.89 times the plain arm's median in two starts that bracket it, for 997 to 1020 MiB
  more on the card. The drafter file named with no `--spec-type` drafts nothing, which is why the
  build writes the two flags as one value. Left open and actionable, with the build above as the
  next landing. A tool-call pair the same morning ran 1.37 times faster with the drafter but
  missed the clock clause, so repricing it is the build's first step.
