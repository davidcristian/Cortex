# The artifact domain rests on a field name convention nothing checks

**Status:** done 2026-09-02
**Area:** repo-checks
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)

The reading is `artifactnames.files(module)`: a settings field names a model artifact when its own
name ends `ARTIFACT_SUFFIX`, which is `_file`. That domain is deliberately the Python name rather
than the environment variable, since the variable is what is under test and a rule whose domain was
the convention it checks could not fail for the misnaming it exists to catch. The cost is that the
question moves one file down rather than away. A future artifact field named `cortex_mmproj_path`,
or `brain_weights`, is outside the domain, is found by nothing and is checked by nothing, which is
the state the projector was in the day before. The four fields the sidecar declares today all use
the suffix.

The compose side has the same shape and a narrower miss. `artifactnames.spends` reads the item after
llama.cpp's own `--model` and nothing else, so a compose service that used a projector variable
after `--mmproj` would name an artifact this reader does not read. No service in this tree does.

## History

- 2026-08-30: opened by the close of
  [R-501](501-the-projector-is-named-in-a-sibling-family-nothing-holds.md), recorded in the artifact
  naming decision of [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md), whose reader finds the
  projector by the field name this entry is about.
- 2026-09-02: closed as the flag reading on the compose side and a derivation the entry did not list
  on the hosted side, recorded in the artifact naming decision of
  [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md). Both hazards were run against the
  committed check first and both passed it silently, the renamed projector field at OK over six
  artifacts. The call the entry asked to revisit produces `("--mmproj", path, ...)` with `path`
  bound one statement earlier from `self._path(...)`, so the flag is readable structurally through a
  local-name hop, and the resolver is what is read instead: a settings field is an artifact when the
  module hands it to `_path`, the one method that joins a file onto `models_root`, whatever the
  field is named and whichever flag or keyword takes the path into the argv. The `_file` suffix
  reading retired with `ARTIFACT_SUFFIX`. Two refusals came with it, a settings method other than
  the resolver reading the mount, and a resolver handed no field at all. The compose side widened
  `ARTIFACT_FLAGS` to `--model` and `--mmproj`, that language having no resolver to read. Opened:
  [R-520](520-the-compose-artifact-flag-set-names-two-of-the-engines-file-flags.md) and
  [R-521](521-a-settings-method-reading-the-mount-for-anything-but-a-path-is-refused.md).
