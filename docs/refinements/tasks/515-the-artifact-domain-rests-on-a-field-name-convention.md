# The artifact domain rests on a field name convention nothing holds

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-30 by the close of
[R-501](501-the-projector-is-named-in-a-sibling-family-nothing-holds.md), which taught
`scripts/artifactnames.py` to find the multimodal projector by the name of the settings field that
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
variable after `--mmproj` would name an artifact this reader walks past. No service in this tree
does; the model host is where a projector is declared, and it is not started by a compose command.
The two halves are one question asked in two languages: what makes an item an artifact when the
flag or the field that carries it is not the one the reader was taught.

**What would close it.** Decide whether the domain can be derived rather than conventional, and
say so where the reader is. Candidates, and they differ in what they rest on:

- **Read the flags llama.cpp names artifacts with**, `--model` and `--mmproj` together, on both
  sides: the compose half is one more entry in the reader's flag set, and the hosted half means
  reading a tier's `extra` for the item after one, which is the tail `hostedtiers.py` refuses to
  approximate because it is assembled by a call. That refusal is the thing to revisit, not to
  route around.
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
