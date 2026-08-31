# The cortex_core barrel at its 300-line cap

**Status:** landed 2026-08-06
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-06 by the ranked-`select` widening ([ADR-0038](../../adr/ADR-0038-ranked-recall.md)).
The 2026-07-14 entry in [tools-mcp.md](../index.md#tools-mcp) bought the barrel its headroom back by halving the
cost of a name from two lines to one (the redundant-alias re-export form, dropping `__all__`). That
economy is spent: the surface is now ~290 names and the file sits at exactly 300 again, which this
change got under only by trimming the module docstring. So the *next* public core name breaks the line
cap for whatever unrelated slice adds it, exactly as before, and there is no second halving available.
The options are all genuine changes of convention rather than economies, which is why this is
recorded rather than done in passing: a sub-barrel per area with `cortex_core` re-exporting it
(still one line per name, so it only moves the problem unless consumers import from the
sub-barrel); the test doubles (`fakes*`) leaving the top barrel, which is a real responsibility
split and is already how a few call sites import them, at the cost of touching many test files;
or the barrel becoming an explicit `__all__` over star imports, which ruff bans as F403. **Fix
when it bites**, which will be the next slice that adds a public core name.
**It bit on 2026-08-06**, the same day, when the summarizing history window added four public
core names (`SummarizingHistoryWindow`, `HistoryRecap`, `RECAP_MAX`, and the widened
`HistoryWindow`). The sub-barrel option was taken, in the only form the record says actually
works: the names live in their defining modules (`cortex_core.summarizing`,
`cortex_core.sessions`, `cortex_core.windowing`) and **every consumer imports from there**, so
the top barrel did not grow by a line and still sits at 300. Three call sites do it
(`cortex_session.store`, the orchestrator's `window_builders`, the tests), each with a comment
naming this entry, joining the one production precedent that already existed
(`cortex_inference.backend` importing `cortex_core.inference`). What this does NOT do is decide
the convention: the barrel is still full, the next name still has to choose, and a
module-by-module escape leaves the tree with two import styles for core names until something
settles which is normal. **Still fix when it bites**, and the fix is now a decision about the
barrel's future rather than a hunt for headroom.

**Landed 2026-08-06, the same night, as the third option in the form its objection missed
([ADR-0026 barrel addendum](../../adr/ADR-0026-prose-style-gates.md)).** The decision this entry
said was owed was taken rather than deferred again, and the criterion was the one the two
earlier attempts had established: whichever option left call sites alone. That ruled out the first two.
A sub-barrel per area only moves the problem unless consumers import from the sub-barrel, and
the test doubles leaving the barrel is a real responsibility split whose cost is 155 files
(measured, `from cortex_core import` across the brain workspace), spent entirely on import
lines. The third option, `__all__` over star imports, is the only one that moves nothing, and
the entry had recorded it as blocked by ruff's F403. It is not: `cortex_core/_surface/` now
holds eight area modules (`ports`, `turn`, `tools`, `subagents`, `memory`, `schedule`,
`residency`, `fakes`), each importing its area's names from their defining modules and
declaring them in its own `__all__`, and `cortex_core/__init__.py` re-exports all eight
wholesale behind one `per-file-ignores` line naming the file and the reason. The second objection came from pyright,
`reportWildcardImportFromLibrary`, which fires because the package resolves
through its own editable install and which a relative import inside the source tree does not
trip, so the barrel is the one relatively-importing file in the brain and needs no suppression.
**The numbers:** 300 lines to 18, 290 public names to 294, and the largest sub-barrel at 151.
`PLAIN_SECURITY_PREAMBLE` is back on the public surface with `HistoryRecap`, `RECAP_MAX` and
`SummarizingHistoryWindow`, which is the whole of the inconsistency the two earlier slices left;
the two production call sites that had imported them from their defining modules with a comment
citing this entry now import them from the barrel like everything else, so the tree is back to
one import style. **Honest about the headroom:** it is per area rather than unlimited, and the
areas are uneven. `ports` at 151 lines has room for about 130 more names and `subagents` at 34
has room for about 250, but a name lands in the area it belongs to rather than the area with
space, so a run of port additions is the case that reaches a cap first. What is different is
that reaching it costs an ordinary split by responsibility inside one area rather than a third
round of this argument, and that the gate was never touched to get here.

## Trail

- 2026-08-06: Opened by the ranked-`select` widening. The economy the 2026-07-14 tools entry
  bought, halving the cost of a name from two lines to one, was spent: the surface was about 290
  names and the file sat at exactly 300 again, with no second halving available.
- 2026-08-06: It bit the same day, when the summarizing history window added four public core
  names. The sub-barrel option was taken in the only form the record says works, the names living
  in their defining modules with every consumer importing from there, so the top barrel did not
  grow; the convention itself was still undecided and the tree carried two import styles.
- 2026-08-06: Landed the same night as the third option, `__all__` over star imports, whose
  recorded ruff F403 block turned out not to hold. `cortex_core/_surface/` now holds eight area
  modules behind one `per-file-ignores` line, and the barrel went from 300 lines to 18 and from
  290 public names to 294, with the largest sub-barrel at 151, every call site unmoved and the
  gate never touched. The headroom is honest rather than unlimited: it is per area and the areas
  are uneven.
