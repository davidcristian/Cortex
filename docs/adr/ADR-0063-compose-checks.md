# ADR-0063: Compose checks: bind defaults, one default per variable, settings reach their service

**Status:** Accepted (2026-09-19)

## Context

The stack is composed from a base file and overrides under `docker/`, run with
`--project-directory .` by the `just` recipes and with a bare `-f docker/<file>` by hand. Three
mistakes in those files pass every language check and fail only at run time:

- A bind mount whose source does not exist yet makes `docker compose up` create a root-owned
  directory in the working tree, filled from inside the container with a GGUF or a database dump,
  one `git add -A` away from the index. Two such directories were found and ignored by hand before a
  check existed.
- One variable written several times with different defaults (`${CORTEX_PG_PASSWORD:-cortex}` three
  times in one override, `${CORTEX_MODELS_DIR:-./models}` in four files) gives a stack whose
  services disagree: Postgres refusing its own clients, or one service reading models from a
  directory the others do not.
- A variable no compose file names never enters the container, whatever the host or `.env` sets, and
  the module inside runs its settings class's default with nothing reported. When this was counted,
  45 of the 89 fields the brain's settings classes read were in that state.

These checks use the standard library only (`scripts/pyproject.toml` declares no dependencies), so
each reads compose with a line reader that raises on any form it was not taught.

## Decision

### Shared

1. **One list of files, and one sentence for a file a reader refuses.** `scripts/composefiles.py`
   finds the compose files (`docker-compose*` and `compose*`, `.yml` or `.yaml`) for every compose
   check, so no check learns about a new override its siblings miss, and each fails when it finds
   none. A file a check's reader refuses is counted apart from the check's findings:
   `composefiles.refused_summary(gate, count, unread)` prints
   `N compose file(s) could not be read, so no <what> in them was checked`, and `faults` lists
   refused files first. `bindcheck.py`, `defaultcheck.py` and `volumecheck.py`
   ([ADR-0067](ADR-0067-image-volume-record.md)) all call it. One level down, each check still
   counts an entry it read but could not ask its question about as a finding
   ([R-694](../refinements/tasks/694-the-bind-and-volume-gates-count-an-entry-they-could-not-ask-about-as-a-finding.md)).

### Bind defaults (`bindcheck.py`)

2. **A bind source must resolve outside the repo, onto a path git tracks, or onto a path git
   ignores.** Outside is the user's disk; tracked is an input compose finds rather than creates
   (`./docker/postgres/init.sql`); ignored is an output declared as one before it is written. "Every
   bind default is gitignored" would be false of every bind onto a shipped file. Git answers both
   questions itself (`ls-files`, `check-ignore` with a trailing slash, since compose creates a
   directory and a directory-only pattern does not match a bare path), because a hand-rolled
   `.gitignore` matcher is the kind of silent error that leaves a check passing.

3. **Both project directories are checked, and a source is checked where it resolves under each.** A
   relative source resolves against `--project-directory` when given and against the first `-f`
   file's directory otherwise, so each source is checked under the repo root and under `docker/`,
   and whether git tracks it is asked for each separately: `./docker/postgres/init.sql` is tracked
   under the root and resolves to nothing under `docker/`. The repo's ignore entries for bind
   targets are therefore unanchored (an anchored `/models/` leaves `docker/models` uncovered, and is
   reported), and `.gitignore` has an anchored `docker/docker/` for the one nested path this
   produces.

4. **Fail closed.** No compose file, a mount entry the reader cannot classify, a source it cannot
   reduce, or a `git` it cannot run is a failure. The reader, `scripts/composemounts.py`, refuses an
   inline `volumes:` list, a mount with no `type`, a type it was not taught, a short-syntax entry
   containing a substitution, and a flow-style entry (`{` or `[`), which would otherwise pass for a
   named volume; it reads a flush sequence, whose items sit at their key's own indent, closing a
   block only on a shallower line or a same-indent line that is not a list item.

### One default per variable (`defaultcheck.py`)

5. **A variable written several times in compose has one default, compared as a value.** Identical
   text agrees; anything else must reduce and render identically through `values.whole_spelling`,
   the function the constant registry renders with, so `8.0` matches `8` (docker parses `8.0g` as a
   size and refuses it, so the memory budget is written both ways deliberately) and `8.5` does not.
   The operators must match first (`${V:-x}` and `${V-x}` disagree about an empty variable, and `:?`
   beside `:-` is one file demanding what another supplies), and only an operator whose argument is
   a value has its argument compared.

6. **It is its own scan, not part of `crosscheck.py`.** The registry compares a value some tree
   declares against the places restating it ([ADR-0042](ADR-0042-cross-tree-constant-registry.md));
   a compose default no tree declares has no such declaration, and the places to compare are each
   other.

7. **What the reader counts as a use is decided.** `scripts/composedefaults.py` consumes `$$` whole
   (compose's literal dollar); reads `${V}` and `$V` as uses with no default, compared on the
   operator alone; reads `${V:-}` as the empty-string default; reads a substitution inside a quoted
   string; skips a whole-line comment; and raises on a `$` opening no known form, a brace that never
   closes, a name that is not an identifier, a nested substitution and a brace inside an argument.

8. **A comment after a value is read as a use, and the report says so.** Compose interpolates the
   strings a YAML parse produced, so a comment is never interpolated, and the reader is wrong about
   a trailing comment. It stays that way
   ([R-385](../refinements/tasks/385-a-note-beside-a-compose-value-is-read-as-a-spend.md),
   declined): telling a comment marker from a `#` inside a scalar needs a quoting model, and block
   scalars, whose content compose does interpolate, break a per-line one on files this repo already
   has. Reading a comment as a use fails visibly; a `#` wrongly read as a comment marker would
   silently drop every use after it. When one `path:line` repeats inside a group, the report adds
   that a comment written after a value looks like this and should move above the line; it offers
   that as the likely reading, since one value can use one variable twice.

9. **A nested default is refused, because it is a second use.** Compose accepts `${A:-${B:-x}}`
   under every operator the reader knows and several levels deep, and it stands for one value with
   nothing set and another once `B` is set, so two uses with different inner names agree under one
   deployment and disagree under another, which a one-value comparison cannot report
   ([R-502](../refinements/tasks/502-the-substitution-reader-refuses-a-nesting-compose-expands.md),
   open). The report quotes the substitution whole: compose ends a substitution containing a `{` at
   the `}` that balances it, counting a bare `{` as well as `${`, so the quotation takes that
   extent, or the text up to the first `}` when none balances. A bare `{` in an argument
   (`${A:-{x}}`) is refused as a brace the reader was not taught rather than called a nested
   substitution
   ([R-691](../refinements/tasks/691-the-substitution-reader-refuses-a-brace-compose-reads-as-text.md)).
   The measurements are in [compose interpolation](../readings/compose-interpolation.md).

### Settings reach their service (`settingscheck.py`)

10. **Every setting a brain module reads is named in the environment of the compose service that
    runs it.** A service is checked when its argv runs `python -m <module>` and exactly one
    `brain/packages/*/src/<module>` exists; the argv is its compose `command`, or the last exec-form
    `CMD` of the Dockerfile it builds, found where `volumecheck.py` finds it. Two files giving one
    service different commands, and a shell-form `CMD`, raise. That covers `brain`, `mcp-email` and
    `model-host` without naming any of them.

11. **The settings are read from the classes without importing them.** `scripts/settingsfields.py`
    treats a class whose `model_config` is a `SettingsConfigDict` call as a settings class; a
    field's variable is its `validation_alias`, else `env_prefix` plus the upper-cased name; a
    `dict` field of a class with `env_nested_delimiter` is also named by any `<NAME>__<entry>` key.
    A form it was not taught raises.

12. **A field counts as named when any compose file lists it under that service's environment**, a
    bare key included, since a key in any overlay reaches the container in the stack that layers it.
    The composed brain receives most settings by bare key (`CORTEX_OUTPUT_GUARDRAIL:`): set on the
    host the value arrives, unset the class default applies, and the default is written only in
    Python. A compose default is kept only where one is needed, and a setting the topology decides
    is set by the file. The base file passes what applies to every stack and each overlay what its
    capability reads ([local-dev-wsl runbook](../runbooks/local-dev-wsl.md)).

13. **A deliberate omission is listed in `EXEMPT`, in the scan, with its reason.** Seven entries:
    the gRPC port and the single-sidecar tools endpoint on the brain, and on the model host the
    three child ports the brain's endpoints dial, the llama-server path the image fixes and the
    models root the mount fixes. An exemption fails when a compose file names its field for the
    service reading it, and when no class read here declares it, so the list cannot outlive its
    reasons. The scan is separate from `defaultcheck.py` and `flagcheck.py`, which also read
    compose, because neither's subject or success line describes this rule.

## Consequences

- `docker compose up` cannot create a directory the index would take, one variable cannot have two
  defaults, and a new setting arrives with its compose key or fails `just check`.
- `--root` for `bindcheck.py` names a git working tree.
- A comment beside a compose value must move above it, and a nested default or a brace in a default
  is refused until a reader is taught the form.
- Each scan runs unconditionally in `just check` and CI, beside the other cross-tree scans.

## Alternatives rejected

- **"Every bind default is gitignored".** False of every bind onto a file the repo ships.
- **Folding the defaults check into `crosscheck.py`.** One scan with two entry points and a subject
  that stops being true.
- **A YAML parser, to read a trailing comment correctly.** A dependency in a dependency-free
  project, bought to allow one comment position.
- **A written package-to-service map for the settings scan.** The argv answers the same question
  from the tree and reaches the sidecars at no cost.

## Related

- [ADR-0026](ADR-0026-prose-style-checks.md) (the prose checks these grew beside),
  [ADR-0062](ADR-0062-shared-check-readers.md) (the tree walk they share),
  [ADR-0067](ADR-0067-image-volume-record.md) (`volumecheck.py`),
  [ADR-0043](ADR-0043-subagent-server-flags.md) (`flagcheck.py`).
- [repo checks](../modules/repo-gates.md), [local-dev-wsl runbook](../runbooks/local-dev-wsl.md),
  [compose interpolation](../readings/compose-interpolation.md).
