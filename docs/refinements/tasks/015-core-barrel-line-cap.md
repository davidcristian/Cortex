# The cortex_core barrel at its 300-line cap

**Status:** done 2026-08-06
**Area:** repo-checks
**Origin:** [ADR-0064](../../adr/ADR-0064-core-public-surface.md)

An earlier change, on 2026-07-14, had halved the cost of a public name in `cortex_core/__init__.py`
from two lines to one, by re-exporting with a redundant alias and dropping `__all__`. That saving
was spent: the public surface reached about 290 names and the file sat at exactly 300 again, which
the change that opened this only got under by trimming the module docstring. The next public core
name would break the line cap for whatever unrelated work added it, and no second halving was
available.

Three options were on the table, all real changes of convention: a sub-barrel per area with
`cortex_core` re-exporting it (still one line per name, so it only moves the problem unless
consumers import from the sub-barrel); the test doubles (`fakes*`) leaving the top barrel, a real
split of responsibility but costing many test files; or an explicit `__all__` over star imports,
which was recorded as blocked by ruff's F403.

It became urgent the same day, when the summarizing history window added four public core names
(`SummarizingHistoryWindow`, `HistoryRecap`, `RECAP_MAX` and the widened `HistoryWindow`). The
sub-barrel option was used as a stopgap, with the names living in their defining modules
(`cortex_core.summarizing`, `cortex_core.sessions`, `cortex_core.windowing`) and three call sites
importing from there, so the top barrel did not grow. That left the tree with two import styles.

Closed the same night with the third option, whose recorded objection did not hold. ruff's F403 is
waived by one `per-file-ignores` line naming the file and the reason, and pyright's
`reportWildcardImportFromLibrary` fires only because the package resolves through its own editable
install, which a relative import inside the source tree avoids, so the barrel is the one
relatively importing file in the brain and needs no suppression. `cortex_core/_surface/` now holds
eight area modules (`ports`, `turn`, `tools`, `subagents`, `memory`, `schedule`, `residency`,
`fakes`), each importing its area's names from their defining modules and declaring them in its
own `__all__`, and `cortex_core/__init__.py` re-exports all eight.

The deciding criterion was which option left call sites alone. A sub-barrel per area only moves
the problem, and moving the test doubles costs 155 files (measured with `from cortex_core import`
across the brain workspace). The numbers: 300 lines to 18, 290 public names to 294, largest
sub-barrel 151 lines. The two call sites that had imported from defining modules now import from
the barrel again, so the tree is back to one import style. The headroom is per area and uneven:
`ports` at 151 lines has room for about 130 more names and `subagents` at 34 has room for about
250, and a name goes where it belongs rather than where there is space, so a run of port additions
reaches a limit first. Reaching it then costs an ordinary split inside one area.

## History

- 2026-08-06: Opened by the ranked `select` widening. The earlier saving of one line per name was
  spent: about 290 names and exactly 300 lines, with no second halving available.
- 2026-08-06: It became urgent the same day, when the summarizing history window added four public
  core names. The sub-barrel option was used as a stopgap, leaving the tree with two import styles.
- 2026-08-06: Closed the same night with `__all__` over star imports, whose recorded ruff F403
  objection did not hold. `cortex_core/_surface/` holds eight area modules behind one
  `per-file-ignores` line; the barrel went from 300 lines to 18 and from 290 public names to 294,
  with every call site unmoved.
