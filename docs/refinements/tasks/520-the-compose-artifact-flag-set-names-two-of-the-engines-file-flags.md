# The compose artifact flag set names two of the engine's file flags

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a compose service in this tree spends a variable after a llama.cpp file flag outside
`ARTIFACT_FLAGS`, a draft model under `--model-draft`, a LoRA adapter under `--lora` or a control
vector, which no service here does today
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-02 by the close of
[R-515](515-the-artifact-domain-rests-on-a-field-name-convention.md), which made the hosted half
of `scripts/artifactnames.py` read the sidecar's resolver, so that a settings field is an artifact
whatever it is named and whichever flag spends it, and left the compose half on a flag list.

`artifactnames.spends` reads the item after either entry of `ARTIFACT_FLAGS`, which names
`--model` and `--mmproj`. Those are the two file flags every server this tree starts spells, and
llama.cpp accepts more: `--model-draft` for speculative decoding, `--lora` for an adapter, and the
control-vector flags, each of which loads a GGUF from the same read-only mount. A compose service
spending `/models/${CORTEX_MODEL_FILE_SUBAGENT_DRAFT:-...}` after `--model-draft` names an artifact
this reader does not read, so a misspelled variable there is held by nothing, which is the shape the
originating close ended on the hosted side. Nothing in `docker/` spends such a flag today, so
nothing is wrong and nothing says so.

The hosted side has no such list. Its domain is the resolver, the one method that joins a file
onto `models_root`, and the originating close records why a compose command has no equivalent: the
mount is written inline as `/models/` and no method resolves anything, so the flag is what that
language offers.

**What would close it.** Two candidates, and they differ in what the reader rests on:

- **Read the flag set off the engine itself.** `llama-server --help` lists every flag and the kind
  of value each takes, and the gate cannot run the image; the pattern for that is the recorded
  answer `volumecheck.py` reads and `just image-volumes` re-derives (ADR-0011 out-of-reach-evidence
  addendum). A recorded list of the engine's file flags, held to the image tag the compose files
  pin, would make a flag added to the engine a diff in the tree rather than a miss in the reader.
- **Read the mount rather than the flag.** Every argv item under the service's models mount is an
  artifact whatever flag precedes it, which also makes the `-m` refusal moot. It needs a name for
  which mount is the models mount, the target `/models` or the source `CORTEX_MODELS_DIR`, and the
  originating close declined it on that ground: a reading resting on that name has the shape of one
  resting on a flag list, with more machinery under it. The ground is worth re-weighing once a third
  flag is really spent, since one name for the mount then holds every flag at once.

## Trail

- 2026-09-02: opened by the close of
  [R-515](515-the-artifact-domain-rests-on-a-field-name-convention.md), recorded in the [ADR-0029
  addendum on the artifact domain being the
  resolver](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-09-02-the-artifact-domain-is-the-resolver-and-the-compose-flag-set-widens),
  whose compose half widened the list by one flag and names this as the residue of a list.
