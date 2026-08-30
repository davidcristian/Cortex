# The projector is named in a sibling family nothing holds

**Status:** landed 2026-08-30
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-30 by the close of
[R-492](492-the-embedder-names-its-artifact-outside-the-family.md), whose argument against a
separate family for non-chat artifacts rests on this one being spelled correctly by a rule that
never reads it.

`scripts/flagcheck.py` holds every model artifact this tree names to beginning
`CORTEX_MODEL_FILE_`, and `scripts/artifactnames.py` finds them structurally in two languages: the
item after llama.cpp's own `--model`, and the settings field a `TierArgs` reads its `model_path`
from. The multimodal projector is a model artifact and is outside both readings on both counts. It
is named after `--mmproj`, not `--model`, and it reaches the cortex tier's argv through `extra`
(`_vision()` in `brain/packages/model_manager/src/cortex_model_manager/config.py`) rather than
through `model_path`, which `hostedtiers.tier_artifacts` is the only thing that reads.

**Nothing is wrong today, and that is the exposure.** `CORTEX_MMPROJ_FILE_CORTEX` reads as a
sibling of `CORTEX_MODEL_FILE_CORTEX`: `CORTEX_`, the kind, `_FILE`, the tier. It got that shape
because it was written beside its neighbours and not because any rule asked for it, which is
exactly the state the naming rule was built to leave behind for the chat artifacts. A second
projector, or a second artifact of some third kind, would be spelled however its author felt and
would redden nothing. The close this entry comes out of found the embedder in that state and it
had drifted; this one has not drifted yet.

**What would close it.** Decide what the family actually is, because the current rule answers with
a prefix and the tree is written in a shape. Two candidate readings, and they differ in what a new
kind of artifact costs:

- **One prefix, and the projector joins it.** `CORTEX_MODEL_FILE_MMPROJ_CORTEX` or similar brings
  it under the shipped rule with no reader change, and pays with a name that says "model file"
  about a thing that is not a model, plus a rename of an operator-facing variable that the vision
  runbook, the GPU runbook and several ADRs spell.
- **A shape, `CORTEX_<KIND>_FILE_<TIER>`, and the rule reads the shape.** Nothing is renamed and
  both existing families are already right, and the rule stops being a `startswith` on one string.
  That means deciding what a legal kind word is, which `subagentservers.MODEL_PREFIX` currently
  gets for free by being the family prefix plus what it serves.

Either way the reader has to grow, since finding the artifact is the harder half: `--mmproj` is
one more flag in `artifactnames.spends`, but the hosted side means reading a tier's `extra` for
artifact-shaped items, and that tail is assembled by a call `hostedtiers.py` deliberately refuses
to approximate. Weigh whether the settings side should be read from the alias declarations
instead, which would find every artifact variable the sidecar declares regardless of which keyword
carries it into the argv, and would need its own answer for what makes a field an artifact.

## Trail

- 2026-08-30: opened by the close of
  [R-492](492-the-embedder-names-its-artifact-outside-the-family.md), recorded in the [ADR-0029
  addendum on a non-chat artifact naming itself in the
  family](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-08-30-a-non-chat-artifact-names-itself-in-the-family-and-the-exclusion-retires),
  whose argument uses this artifact as the evidence that the split between the tree's two spellings
  is a word order rather than a category.
- 2026-08-30: landed as the rename plus the reading that finds it, recorded in the [ADR-0029
  addendum on the projector joining the
  family](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-08-30-the-projector-joins-the-family-and-a-field-is-read-for-its-own-name).
  The variable is `CORTEX_MODEL_FILE_CORTEX_MMPROJ`, and `artifactnames.files(module)` reads every
  settings field whose own name ends `_file`, so the artifact that rides `extra` is found without
  the tier reader approximating a tail it refuses to. **The shape reading this entry offered was
  refused on the membership readers rather than on taste**: a free kind word admits
  `CORTEX_SUBAGENT_MODEL_FILE_CPU`, the exact variable the naming rule exists to catch, and a
  closed kind vocabulary is a hand-maintained two-word registry whose second member has one
  instance. The word order was decided the same way, the tier staying immediately after the prefix
  because `MODEL_PREFIX` is the family prefix plus what it serves, so a subagent tier's projector
  stays inside the membership reading. The rename's cost is one operator-facing variable whose
  stale spelling starts the cortex text-only and drops `capture_screen` from the advertisement, a
  visible failure rather than a silent one, named in `docs/runbooks/vision.md`; no `.env` is
  tracked or present here. What this close opened is one level down and is
  [R-515](515-the-artifact-domain-rests-on-a-field-name-convention.md): the domain is now a field
  name convention nothing holds, and a compose argv naming a projector after `--mmproj` is still
  unread.
