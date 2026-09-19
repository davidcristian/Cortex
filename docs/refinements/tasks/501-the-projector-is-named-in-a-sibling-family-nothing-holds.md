# The projector is named in a sibling family nothing checks

**Status:** done 2026-08-30
**Area:** repo-checks
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)

`scripts/flagcheck.py` requires every model artifact this tree names to begin with
`CORTEX_MODEL_FILE_`, and `scripts/artifactnames.py` finds them structurally in two languages: the
item after llama.cpp's own `--model`, and the settings field a `TierArgs` reads its `model_path`
from. The multimodal projector is a model artifact and is outside both readings on both counts. It
is named after `--mmproj`, not `--model`, and it reaches the cortex tier's argv through `extra`
(`_vision()` in `brain/packages/model_manager/src/cortex_model_manager/config.py`) rather than
through `model_path`.

Nothing was wrong, and that is the exposure. `CORTEX_MMPROJ_FILE_CORTEX` reads as a sibling of
`CORTEX_MODEL_FILE_CORTEX`: `CORTEX_`, the kind, `_FILE`, the tier. It got that shape because it was
written beside its neighbours and not because any rule asked for it, which is the state the naming
rule was built to leave behind for the chat artifacts. A second projector, or an artifact of a third
kind, would be named however its author felt and would fail no check.

## History

- 2026-08-30: opened by the close of
  [R-492](492-the-embedder-names-its-artifact-outside-the-family.md), recorded in the artifact
  naming decision of [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md), whose argument uses
  this artifact as the evidence that the split between the tree's two naming styles is a word order
  rather than a category.
- 2026-08-30: closed as the rename plus the reading that finds it, recorded in the artifact naming
  decision of [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md). The variable is
  `CORTEX_MODEL_FILE_CORTEX_MMPROJ`, and `artifactnames.files(module)` reads every settings field
  whose own name ends `_file`, so the artifact that reaches the argv through `extra` is found
  without the tier reader approximating a tail it refuses to read. The alternative of reading a
  general `CORTEX_<KIND>_FILE_<TIER>` shape was refused on the membership readers rather than on
  taste: a free kind word admits `CORTEX_SUBAGENT_MODEL_FILE_CPU`, the exact variable the naming
  rule exists to catch, and a closed kind vocabulary is a hand-maintained two-word registry whose
  second member has one instance. The word order was decided the same way, the tier staying
  immediately after the prefix because `MODEL_PREFIX` is the family prefix plus what it serves. The
  rename's cost is one operator-facing variable whose stale name starts the cortex text-only and
  drops `capture_screen` from the advertisement, a visible failure rather than a silent one, named
  in `docs/runbooks/vision.md`; no `.env` is tracked or present here. Opened by this close:
  [R-515](515-the-artifact-domain-rests-on-a-field-name-convention.md).
