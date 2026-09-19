# MTP (multi-token-prediction) model variants

**Status:** done 2026-09-19
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

A drafter model lets the engine predict several tokens at once and check them against the real
model, which trades VRAM for decode speed. [ADR-0004](../../adr/ADR-0004-model-lineup.md)
deferred it until the latency saved was worth the memory spent.

It shipped 2026-09-19 for the deep tier alone. `CORTEX_MODEL_FILE_BRAIN_DRAFT` names that tier's
drafter and is empty by default. When a file is named, `drafter_flags` in `tiers.py` appends
`--model-draft PATH --spec-type draft-mtp` to the tier's `extra`, always as a pair, because the
path alone was measured to draft nothing. The compose line, the drafter's cost beside
`CORTEX_SWAP_BRAIN_VRAM_MIB`, and the runbook's three settings (evict the GPU subagent tier,
raise the VRAM figure, keep co-residency off) shipped with it.

The artifact is `google/gemma-4-31B-it-assistant/assistant-F16.gguf` (954843360 bytes,
`general.architecture` `gemma4-assistant`), which serves the deep pick
`google/gemma-4-31B-it-qat-q4_0-gguf/gemma-4-31B_q4_0-it.gguf` chosen on 2026-08-04. The drafter
setting keeps its empty default because the drafter serves only that pick.

The drafter goes in the tier's `extra`, as the vision projector does, rather than in a field of
its own on `TierArgs`: `scripts/hostedtiers.py` reads `llama_server_argv` as one tuple with
exactly one splat and fails on a second. `scripts/artifactnames.py` finds the new field through
its `_path` call, so `flagcheck.py` now counts eight artifacts, and `scripts/settingscheck.py`
failed until the compose line was written.

## History

- 2026-08-16: Priced against the tree and given a trigger, and both lines of the origin now read
  differently. The memory cost is survivable on the tier that wants this: gemma-4-31B alone reads
  20671 to 20723 MiB, a 2878 MiB peer beside it reads 23555 to 23642 MiB with about 908 MiB free,
  and the deep model's decode is unharmed at 28.92 to 29.82 tok/s against 25.07 to 33.28 alone. It
  is fatal only for the cortex-plus-deep pairing, which needs 29139 MiB against 24463. The latency
  condition had arguably already arrived, a deep turn spending 3800 to 4500 tokens at about 31
  tok/s, roughly two minutes of generation on top of a 99.6 s load.
- 2026-08-16: What blocked it was neither of those. Nothing in the tree could name such an
  artifact or hand it to a server: no `--model-draft`, no draft or speculative flag of any
  kind, and no MTP filename. `llama_server_argv` builds a fixed flag tuple plus a per-tier
  `extra` whose only producers were the thinking-off pair and the vision tail, and the roster is
  fixed at boot on purpose, since a request-supplied argv would be remote code execution against
  the GPU container.
- 2026-09-06: Checked against the mount and the fixed engine build; not fired. Six MTP artifacts were
  on the mount, three under `unsloth/` and three under `llmfan46/`, each a same-file variant
  rather than a separate draft model: the MTP `Qwen3.5-9B-UD-Q4_K_XL.gguf` is 6135034208 bytes
  against 5966095584 for its non-MTP twin. None was a shipped pick.
- 2026-09-06: The engine half of the deferral expired. Both cached tags reported
  `version: 0.3.0-dev (build 10680, commit d7bd3bfca)` and advertised `--spec-draft-model, -md,
  --model-draft FNAME` with the rest of the speculative family. The tree half still held.
- 2026-09-11: Read again; not fired. The same six MTP directories, both shipped picks unchanged
  and present (the cortex file at 6975879296 bytes, the subagent file at 5154941280), both cached
  tags still build 10680, and the grep for draft flags still returning only one sentence in
  `fakes_model_host.py`.
- 2026-09-17: The first half of the trigger had fired before it was written, and two earlier
  readings here were wrong. `google/gemma-4-31B-it-assistant/` and
  `google/gemma-4-26B-A4B-it-assistant/` had been on the mount since 2026-08-16; each
  `config.json` names `Gemma4AssistantForCausalLM`, with a `backbone_hidden_size` of 5376 and
  2816, their model card calls them the MTP drafters for Gemma 4, and each holds an
  `assistant-F16.gguf` whose header reads `gemma4-assistant`. So "the mount holds no gemma MTP
  artifact at all" and "no MTP or draft artifact under `google/`" were both false, as was "the
  deep pick is still open", the deep pick having been made on 2026-08-04. The engine was read
  without starting anything, by extracting `/app` from a `docker create` of the cached `:server`
  tag: `libllama.so.0.3.0` holds `llama_model_gemma4_assistant` and
  `/app/src/models/gemma4-assistant.cpp`, and `libllama-common.so.0.3.0` names `--model-draft`,
  `--spec-type`, `--draft-max`, `--gpu-layers-draft` and the message
  `creating MTP draft context against the target model`.
- 2026-09-17: The load and decode reading was taken with the card to itself, and the drafter pays.
  Both runs used the deep tier's shipped argv (`-ngl 99 --ctx-size 8192 --parallel 1 --jinja
  --cache-ram 0`), one untimed warm-up then four timed requests of one fixed prompt at
  `max_tokens` 512 and seed 42. Decode ran at 1.86 and 1.89 times the plain median in two starts
  that bracket it, against a plain spread of 0.02 of that median, for 997 to 1020 MiB more on the
  card. Acceptance was 328 of 548 drafted tokens (0.60, mean accepted length 2.79). The decode
  clocks were 0.48 of maximum with the drafter and 0.57 without, inside the tenth the rule
  allowed. `draft-simple` was not needed, and the drafter named with no `--spec-type` drafted
  nothing. A tool-call pair the same morning ran 1.37 times faster with the drafter, acceptance 46
  of 123 (0.37, mean length 2.12), every reply in both runs ending in the same `search_email` call
  after 86 tokens with the drafter and 69 without, but the clock clause failed at 0.45 against
  0.62, so that pair did not decide. Run logs are under `measurements/mtp-2026-09-17/` on the
  host.
- 2026-09-19: Shipped. Two card runs the same day priced a tool-call turn and an answer-text turn
  at 1.34 times the plain rate under one power ceiling, and the model-swap runbook now names the
  drafter wherever the deep pick is named.
