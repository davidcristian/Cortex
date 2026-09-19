# The compose artifact flag set names two of the engine's file flags

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Trigger:** a compose service in this tree uses a variable after a llama.cpp file flag outside
`ARTIFACT_FLAGS`, a draft model under `--model-draft`, a LoRA adapter under `--lora` or a control
vector, which no service here does today. That is countable by reading the command of every
service the compose files start and listing the flags it uses
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)
**Verified:** 2026-09-19

`artifactnames.spends` reads the item after either entry of `ARTIFACT_FLAGS`, which names `--model`
and `--mmproj`. Those are the two file flags every server this tree starts uses, and llama.cpp
accepts more: `--model-draft` for speculative decoding, `--lora` for an adapter, and the
control-vector flags, each of which loads a GGUF from the same read-only mount. A compose service
writing `/models/${CORTEX_MODEL_FILE_SUBAGENT_DRAFT:-...}` after `--model-draft` names an artifact
this reader does not read, so a misnamed variable there is checked by nothing.

The hosted side has no such list: its domain is the resolver, the one method that joins a file onto
`models_root`. Two options for the compose side. Record the engine's own file flags, read off
`llama-server --help`, in the shape `volumecheck.py` reads and `just image-volumes` recomputes,
which makes a flag added to the engine a diff in the tree rather than a miss in the reader. Or read
the mount rather than the flag: every argv item under the service's models mount is an artifact
whatever flag precedes it, which needs a name for which mount is the models mount, the target
`/models` or the source `CORTEX_MODELS_DIR`.

## History

- 2026-09-02: opened by the close of
  [R-515](515-the-artifact-domain-rests-on-a-field-name-convention.md), recorded in the artifact
  naming decision of [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md), whose compose half
  widened the list by one flag.
- 2026-09-04: checked and left open. Reading the command of every service the compose files start
  turns up thirteen distinct flags and no file flag outside `ARTIFACT_FLAGS`: `--model` in three
  services, `llama-embed`, `llama-subagent` and `llama-subagent-qwen`, which are the three artifacts
  `artifactnames.composed` finds, and nothing named `--model-draft`, `--lora` or a control vector.
  `--mmproj` appears in no compose command either; the cortex tier's projector pair is written by
  the sidecar's own argv in `cortex_model_manager/config.py`. The two short flags a command does use
  are the shapes the reader declines by name: `python -m cortex_email` starts the email sidecar, and
  `sh -c` runs the filesystem sidecar's install line.
- 2026-09-14: counted again and the trigger has not fired. The same walk turns up fifteen distinct
  flags rather than thirteen, the two added being `--cache-ram` on both subagent services, which
  takes a count and not a file. No file flag outside `ARTIFACT_FLAGS` appears anywhere.
- 2026-09-15: counted again after the flag check gained a thread-count requirement, and the trigger
  has not fired. The same fifteen flags: the new requirement asks for `--threads`, which both CPU
  servers already used, so nothing was added to any command.
- 2026-09-19: counted again after the settings pass-through and the settings scan added environment
  entries to three compose files, and the trigger has not fired. Neither change wrote a command, so
  the same fifteen distinct flags appear. The only file flag among them is `--model`, used by
  `llama-embed`, `llama-subagent` and `llama-subagent-qwen`, and `artifactnames.ARTIFACT_FLAGS` is
  still `("--model", "--mmproj")`, with `--mmproj` in no compose command.
