# The set a subagent server joins is a naming convention nothing enforces

**Status:** done 2026-08-29
**Area:** repo-checks
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)

`flagcheck.py` runs one rule over two sets, and both decide whether something is a subagent server
out of `subagentservers.MODEL_PREFIX`, the string `CORTEX_MODEL_FILE_SUBAGENT`. A compose service
qualifies when its command uses a variable beginning that way; a hosted tier qualifies when the
settings field holding its `model_path` is aliased to a variable beginning that way. Three settings
follow the convention today and the readers are right about all three.

Nothing requires a fourth to follow it. A subagent artifact named
`CORTEX_SUBAGENT_MODEL_FILE_CPU`, or `CORTEX_MODEL_SUBAGENT_FILE_CPU`, is the same artifact under a
variable neither reader looks at, so the server or tier it names falls out of both sets with
nothing reported. The promise is that a server added tomorrow is checked the day it is written, and
that promise rested on the next author writing one variable the way three earlier ones were
written.

## History

- 2026-08-28: opened by the close of
  [R-467](467-the-hosted-subagent-tier-meets-the-flag-rule-by-hand.md), which gave the hosted tier
  the same membership test the compose side already used and left the test resting on a convention.
- 2026-08-29: closed as the artifact naming rule of
  [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md), a second rule in the same scan:
  `scripts/artifactnames.py` returns every model artifact this tree names and `scripts/flagcheck.py`
  requires each to begin with `CORTEX_MODEL_FILE_`. Both placements were mutated against the
  committed check first, and the entry was right: renaming the sidecar's alias out of the family and
  deleting that tier's reasoning-off tail printed `flagcheck OK: the 2 subagent server(s)` and
  exited 0. The model_manager suite asserts all three aliases through the environment it sets, so
  renaming one fails the brain suite, while nothing said anything about a fourth arriving. The
  entry's own preferred fix was rejected as circular: requiring the `CORTEX_MODEL_FILE_*` family to
  be closed makes the rule's domain the prefix whose use it checks, so
  `CORTEX_SUBAGENT_MODEL_FILE_CPU` would be outside it and the check could not fail for the fault it
  was built for. The artifacts are found structurally instead, the item after llama.cpp's own
  `--model` and the settings field a tier reads its `model_path` from, so the structural reading
  enumerates and the prefix judges. The registry alternative was declined, since it would compare
  the three names the brain suite already asserts and say nothing about the fourth. Three
  exclusions are deliberate and argued: the short form of the model flag, an item using no variable,
  and an argv declaring `--embeddings`. That last leaves a live counterexample in the tree, which is
  [R-492](492-the-embedder-names-its-artifact-outside-the-family.md).
