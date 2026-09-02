# The artifact domain rests on a field name convention nothing holds

**Status:** landed 2026-09-02
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-30 by the close of
[R-501](501-the-projector-is-named-in-a-sibling-family-nothing-holds.md), which made
`scripts/artifactnames.py` find the multimodal projector by the name of the settings field that
declares it.

The reading is `artifactnames.files(module)`: a settings field names a model artifact when its own
name ends `ARTIFACT_SUFFIX`, which is `_file`. That domain is deliberately the Python name rather
than the environment variable, since the variable is the spelling under test and a rule whose
domain was the convention it checks could not fail for the misspelling it exists to catch. **The
cost is that the question moves one file down rather than away.** A future artifact field named
`cortex_mmproj_path`, or `brain_weights`, is outside the domain, is found by nothing and is held
by nothing, which is exactly the state the projector was in the day before that close. The four
fields the sidecar declares today all spell the suffix, so nothing is wrong and nothing says so.

The compose side has the same shape and a narrower miss. `artifactnames.spends` reads the item
after llama.cpp's own `--model` and nothing else, so a compose service that spent a projector
variable after `--mmproj` would name an artifact this reader does not read. No service in this tree
does; the model host is where a projector is declared, and it is not started by a compose command.
The two halves are one question asked in two languages: what makes an item an artifact when the
flag or the field that carries it is not one the reader was written for.

**What would close it.** Decide whether the domain can be derived rather than conventional, and
say so where the reader is. Candidates, and they differ in what they rest on:

- **Read the flags llama.cpp names artifacts with**, `--model` and `--mmproj` together, on both
  sides: the compose half is one more entry in the reader's flag set, and the hosted half means
  reading a tier's `extra` for the item after one, which is the tail `hostedtiers.py` deliberately does
  not approximate, because it is assembled by a call. That decision is the thing to revisit, not
  to route around.
- **Hold the field name convention itself**, the way the family prefix is now held: a rule that
  every settings field whose value flows into an artifact path is named `_file`. It needs its own
  answer for what "flows into an artifact path" means without evaluating the module, which is the
  same wall the first candidate hits from the other side.
- **Argue the convention and stop there**, recording that a field name is a cheap thing to get
  right and that the gate reports the artifacts it can see. Honest, and it is the state this entry
  describes; writing it down where the reader is would at least make the next author's miss a
  documented one rather than a silent one.

## Trail

- 2026-08-30: opened by the close of
  [R-501](501-the-projector-is-named-in-a-sibling-family-nothing-holds.md), recorded in the
  [ADR-0029 addendum on the projector joining the
  family](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-08-30-the-projector-joins-the-family-and-a-field-is-read-for-its-own-name),
  whose reader finds the projector by the field name this entry is about.
- 2026-09-02: landed as the first candidate on the compose side and a derivation the entry did not
  list on the hosted side, recorded in the [ADR-0029 addendum on the artifact domain being the
  resolver](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-09-02-the-artifact-domain-is-the-resolver-and-the-compose-flag-set-widens).
  Both hazards were run against the committed gate first and both passed it silently, the renamed
  projector field at OK over six artifacts. The call the entry asked to revisit produces
  `("--mmproj", path, ...)` with `path` bound one statement earlier from `self._path(...)`, so
  the flag is readable structurally through a local-name hop, and the resolver is what is read
  instead: a settings field is an artifact when the module hands it to `_path`, the one method
  that joins a file onto `models_root`, whatever the field is named and whichever flag or keyword
  spends the path. The `_file` suffix reading retired with `ARTIFACT_SUFFIX`. Two refusals came
  with it, a settings method other than the resolver reading the mount, and a resolver handed no
  field at all. The compose side widened `ARTIFACT_FLAGS` to `--model` and `--mmproj`, that
  language having no resolver to read. What this close opened:
  [R-520](520-the-compose-artifact-flag-set-names-two-of-the-engines-file-flags.md), the compose
  flag list the engine can outgrow, and
  [R-521](521-a-settings-method-reading-the-mount-for-anything-but-a-path-is-refused.md), the
  refusal's cost on a read of the mount that joins nothing.
