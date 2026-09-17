# Nothing holds the compose brain to its settings classes

**Status:** landed 2026-09-17
**Area:** repo-gates
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

Since [R-686](686-the-compose-brain-cannot-receive-most-of-its-settings.md) landed, every setting
the orchestrator package reads reaches the brain container from some compose file, except
`CORTEX_SEAM_PORT` and `CORTEX_TOOLS_ENDPOINT`, which are unnamed on purpose. Nothing keeps that
true. A field added to any of the eleven settings classes reaches no container until somebody
remembers to add a key, and the failure is silent: the brain runs the Python default and no
error names the setting. That is how 45 of 89 fields came to be unnamed.

No existing check can hold it. The scripts that read compose files (`composestarts.py` reads each
service's environment block, bare keys included) have no reader for settings classes, and the
brain's own tests, which could import the classes, have no compose reader: the brain environment
carries no YAML library, and these gates are stdlib-only by design.

**What would be built.** A twelfth cross-tree scan, `scripts/settingscheck.py`, with:

- a reader, `scripts/settingsfields.py`, that parses the modules under
  `brain/packages/orchestrator/src/` without importing them, finds each class whose `model_config`
  is a `SettingsConfigDict` call, and derives each annotated field's environment name: the
  `validation_alias` keyword when it is a string (resolved through `moduleconstants.py` when it
  names a constant), else the `env_prefix` plus the field name in upper case. A field whose class
  sets `env_nested_delimiter` and whose annotation is a `dict` is a map, satisfied by its own name
  or by any `NAME__<key>` key. A class whose prefix or alias the reader cannot reduce raises, as
  every reader here does for a shape it was not taught.
- the one mapping the tree does not state: the orchestrator package runs in the `brain` service.
  `model_manager` in `model-host` and `email` in `mcp-email` are the same question for the
  sidecars, and are cheap to add once the reader exists.
- the verdict: fail when a field's name appears as a key in the `brain` environment of no compose
  file under `composefiles.py`'s walk, unless it is on a short exemption list carried in the scan,
  each exemption with its reason; and fail when an exemption is stale, meaning some file names it
  or no class reads it.
- the success line naming the classes, fields and files read, with a floor on the class count so
  a reader that silently finds nothing fails.

Landing it changes every list that names the scans together: `AGENTS.md` (the count and the
roster), the `justfile`'s `check` recipe and a new `check-settingscheck`, the CI workflow, the
repo-gates module doc, and `scanrecipes.py`, which `rostercheck.py` holds those lists to. The
proof is a mutation table over `cd scripts && uv run pytest`, and the live proof is deleting one
bare key from `docker/docker-compose.yml` and watching the scan fail.

## Trail

- 2026-09-17: filed by [R-686](686-the-compose-brain-cannot-receive-most-of-its-settings.md), which
  landed the pass-through and left this gate out of the same change. Recorded in the ADR-0015
  addendum of 2026-09-17 on the composed brain.
- 2026-09-17: landed as `scripts/settingscheck.py` and `scripts/settingsfields.py`, recorded in
  the [ADR-0026 addendum of 2026-09-17](../../adr/ADR-0026-prose-style-gates.md).
  Two parts of the design above changed. The services are found by the module their argv runs,
  in a compose command or the Dockerfile's `CMD`, rather than by a written package-to-service
  mapping, so the sidecars were held from the start; that found three model-host fields no file
  named, now passed bare, and five model-host exemptions beside the brain's two. And
  `scanrecipes.py` needed no change, since it reads the scan list from the justfile and CI.
