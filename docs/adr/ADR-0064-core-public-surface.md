# ADR-0064: The core's public API is re-exported by area

**Status:** Accepted (2026-08-06)

## Context

`cortex_core/__init__.py` is the brain core's public API: every port, value type, core function and
test double is importable as `from cortex_core import X`, and every package and suite in the brain
imports that way. The file listed each name itself, and it reached the 300-line cap
([ADR-0001](ADR-0001-architecture.md), decision 6): one change fit only by trimming that file's
docstring, and the next left a public core constant importable from its defining module alone,
because adding it to the re-export file measured 304 lines. That is the line cap deciding a public
API rather than a file's length.

## Decision

1. **The re-export file re-exports one sub-module per area.** `cortex_core/_surface/` holds one
   module per area of the core (`ports`, `turn`, `tools`, `subagents`, `memory`, `schedule`,
   `residency`, `logs`, `fakes`), each importing its area's names from their defining modules and
   declaring them in its own `__all__`, and `cortex_core/__init__.py` star-imports each.
   `from cortex_core import X` reaches every public name, so no call site moved. A new public name
   costs a line in its area's file and none in `__init__.py`; when an area file nears the cap, it is
   split by responsibility like any other module.

2. **The star import is allowed in that one file, and it is relative.** Ruff's F403 is suppressed by
   a `per-file-ignores` entry in `ruff.toml` naming that file, since its reason ("unable to detect
   undefined names") does not apply to a source module declaring `__all__`. Pyright strict refuses a
   wildcard from a library (`reportWildcardImportFromLibrary`), which fires because `cortex-core`
   resolves through its own editable install; `from ._surface.turn import *` resolves inside the
   source tree instead and type-checks with no suppression. That file is therefore the one place in
   the brain that imports relatively.

3. **Nothing outside the package names `_surface`.** The areas are an internal split of one API, and
   [brain-core.md](../modules/brain-core.md) documents which names each holds.

## Consequences

- The line cap measures each area file like any other module, and `__init__.py` stays a short list
  of imports. Room to grow is per area rather than shared.
- No exemption was added to the cap, and nothing outside the cap's documented exceptions changed.

## Alternatives rejected

- **The test doubles leaving the public API**, or one sub-module per area imported by name. Either
  only moves the limit unless every consumer is rewritten, which is 155 files for the doubles alone.
- **An exemption from the line cap for `__init__.py`.** The cap's exceptions are argued one by one
  and a public API growing is not one.

## Related

- [ADR-0001](ADR-0001-architecture.md) (the line cap), [brain-core.md](../modules/brain-core.md).
