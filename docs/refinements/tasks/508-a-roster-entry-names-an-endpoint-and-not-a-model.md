# A roster entry names an endpoint, and nothing says which model answers there

**Status:** declined 2026-09-02
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

Opened 2026-08-30 by the closes of
[R-482](482-the-sentence-is-one-wording-for-every-entry.md) and
[R-485](485-a-roster-description-never-says-whether-the-entry-answers.md), which declined a
per-entry wording and a per-entry answer rate for the same reason: the entry a value would hang on
does not fix the model whose behaviour the value describes.

`SubagentProfile` is keyed by roster name. `SubagentResources.request.model` and the resident id
inside `SingleResidentModelManager(name, endpoint)` are both that same name, matched against itself
and never sent anywhere that could disagree; what the backend actually does is dial `endpoint`. The
weights are named in a `command:` argument of a `llama-server` container,
`CORTEX_MODEL_FILE_SUBAGENT` for the default entry and `CORTEX_MODEL_FILE_SUBAGENT_QWEN` for the
alternate, in a compose file the brain never reads. So the brain knows which endpoint it dials and
has no way to learn which model answers, and every per-entry claim this repo has measured is
attached to an artifact the roster cannot name.

**The server does answer the question.** `GET /props` reports `model_path` and `model_alias`, both
the container-side path of the loaded GGUF, and `GET /v1/models` reports the same string as the
model's name. Confirmed live 2026-08-30 by the agent on
`ghcr.io/ggml-org/llama.cpp:server@sha256:db057ec90de0a423255a218b9612420993237ff33db68b3155dc3bba9b994a20`,
one CPU server on `Qwen3.5-0.8B-Q8_0.gguf` under the subagent compose file's own flags, which
reported `/models/unsloth/Qwen3.5-0.8B-GGUF/Qwen3.5-0.8B-Q8_0.gguf` in all three fields. That is one
HTTP call against a server that is already up, and it is the cheapest identity this tier has.

**The precedent is already in the tree.** `cortex_orchestrator.vision` probes `GET {endpoint}/props`
for a tier's modalities, parses defensively, fails closed on any error, and was moved from a
startup reading to a per-advertisement one precisely because the process it describes is not the
brain's: the model host recreates a `llama-server` child with whatever argv its own boot gave it, so
a redeployment flips the answer under a brain that never restarts. A roster entry's artifact has
exactly that shape, and the probe's own latency was measured there at 1.5 to 2.5 ms.

**What has to be decided rather than typed.** Four things, and the second is the one that could
sink it.

- **What it does with the answer.** Logging each entry's artifact once at wiring is the cheap
  version and is probably right, since it puts the pick in the same place an operator already reads
  the endpoint. Warning needs something to compare against, and refusing to serve is wrong: an
  entry serving an artifact nobody expected still answers.
- **Whether an expectation is declarable at all.** There is no field today saying which artifact an
  entry should be serving, and adding one is a config knob that can be wrong in a new way, since it
  is typed by the same hand that typed the compose `command:` and would drift from it with nothing reporting the drift.
  Without an expectation the probe reports rather than checks, which may be the whole honest scope.
- **Where it lives.** Per advertisement, like the vision probe, would cost an HTTP call per spawn
  spec for a value that changes only on a container restart; once at `build_subagents` costs
  nothing per turn and goes stale on exactly the redeployment the vision probe moved to catch.
- **A container path is not an identity.** A renamed file, a requantized artifact at the same path
  or a bind mount pointed elsewhere all read the same, so what this can honestly report is the path
  the server was started on and not which weights they are.

**What it would unblock.** Both closes above name it as the thing that would reopen them: a
per-entry value filed under something that determines the behaviour it describes. It would also let
the subagent runbook's override table be read against a running stack rather than against a compose
default, which is the table both closes chose as the home for the row's measured rates.

## Trail

- 2026-08-30: opened by the closes of
  [R-482](482-the-sentence-is-one-wording-for-every-entry.md) and
  [R-485](485-a-roster-description-never-says-whether-the-entry-answers.md), which found the same
  missing identity under two different per-entry values.
- 2026-09-02: the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md) declined the per-entry
  flag it was circling without needing this entry. The budget alone measured worse than the pair on
  the gemma pick and inert on the Qwen pick, so there is no per-family flag set to express and the
  flag gate's one rule stands. The identity question here is untouched.
- 2026-09-02: **declined**, by the ADR-0018 artifact addendum. Re-derived: every claim about the
  wiring held, `/props` was read again on the shipped default pick at the image digest above and
  reports the compose variable joined under `/models` in both fields, and `/v1/models` reports the
  same string as the model's `id` beside an empty `digest`. Two claims did not hold: the brain's
  boot log carries no roster line for an artifact to sit beside (`build_subagents` logs nothing),
  and neither decline above would reopen on identity alone, each having given two further reasons
  that stand whatever an entry carries. Declined because the brain speaks logical ids by decision
  and no decision in it reads which weights answer; because a path is not an identity, which the
  server's own empty `digest` confirms; and because the one placement the repo's own rule allows,
  per call, buys a value nothing acts on, while once at wiring goes stale under exactly the
  redeployment that changes it. The runbook's override table now says how the row a running stack
  is on is read off the server. Opened
  [R-527](527-one-roster-entrys-two-targets-are-named-by-two-artifact-variables.md), the one
  expectation a `/props` read could be held to without a knob: an entry's two placement targets
  naming one artifact.
