# A roster entry names an endpoint, and nothing says which model is loaded there

**Status:** declined 2026-09-02
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

`SubagentProfile` is keyed by roster name. `SubagentResources.request.model` and the resident id
inside `SingleResidentModelManager(name, endpoint)` are both that same name, matched against itself
and never sent anywhere that could disagree; what the backend does is dial `endpoint`. The weights
are named in a `command:` argument of a `llama-server` container,
`CORTEX_MODEL_FILE_SUBAGENT` for the default entry and `CORTEX_MODEL_FILE_SUBAGENT_QWEN` for the
alternate, in a compose file the brain never reads. So the brain knows which endpoint it dials and
has no way to learn which model is loaded, and every per-entry claim this repo has measured is
attached to an artifact the roster cannot name.

The server does answer the question. `GET /props` reports `model_path` and `model_alias`, both the
container-side path of the loaded GGUF, and `GET /v1/models` reports the same string as the model's
name. Confirmed live 2026-08-30 on
`ghcr.io/ggml-org/llama.cpp:server@sha256:db057ec90de0a423255a218b9612420993237ff33db68b3155dc3bba9b994a20`,
one CPU server on `Qwen3.5-0.8B-Q8_0.gguf` under the subagent compose file's own flags, which
reported `/models/unsloth/Qwen3.5-0.8B-GGUF/Qwen3.5-0.8B-Q8_0.gguf` in all three fields. That is one
HTTP call against a server that is already up. A container path is not an identity, though: a
renamed file, a requantized artifact at the same path or a bind mount pointed elsewhere all read the
same.

## History

- 2026-08-30: opened by the closes of
  [R-482](482-the-sentence-is-one-wording-for-every-entry.md) and
  [R-485](485-a-roster-description-never-says-whether-the-entry-answers.md), which declined a
  per-entry wording and a per-entry answer rate for the same reason: the entry a value would hang on
  does not fix the model whose behaviour the value describes.
- 2026-09-02: the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md) declined the per-entry flag
  it was circling without needing this entry. The budget alone measured worse than the pair on the
  gemma pick and had no effect on the Qwen pick, so there is no per-family flag set to express.
- 2026-09-02: declined, by ADR-0018 decision 11. Every claim about the wiring held, `/props` was
  read again on the shipped default pick at the image digest above and reports the compose variable
  joined under `/models` in both fields, and `/v1/models` reports the same string as the model's
  `id` beside an empty `digest`. Two claims did not hold: the brain's boot log has no roster line
  for an artifact to sit beside (`build_subagents` logs nothing), and neither decline above would
  reopen on identity alone, each having given two further reasons. Declined because the brain uses
  logical ids by decision and no decision in it reads which weights are loaded; because a path is
  not an identity, which the server's own empty `digest` confirms; and because the one placement the
  repo's own rule allows, per call, buys a value nothing acts on, while once at wiring goes stale
  under exactly the redeployment that changes it. The runbook's override table now says how to read
  off the server which row a running stack is on. Opened
  [R-527](527-one-roster-entrys-two-targets-are-named-by-two-artifact-variables.md).
