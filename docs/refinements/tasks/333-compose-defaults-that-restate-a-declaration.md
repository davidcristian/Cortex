# Which compose defaults restate a declaration has never been surveyed

**Status:** done 2026-08-21
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

The constant scan reaches a compose default, and eight entries use that: the salience limit, the
two brain-to-body deadlines, the log rendering, and the five subagent settings. Every one was found
by reading the file somebody happened to be editing.

About fifty `${CORTEX_*:-default}` substitutions live under `docker/`. Most name a path, a model
file, a port, or a machine-specific number that no Python constant declares, and those have nothing
on the other side to disagree with. Some restate a default the brain or the body declares, and each
of those is the divergence the scan exists to report. Nobody had read the fifty and sorted them
into the two groups, so the count of unregistered restatements was unknown rather than small.

Closing it means reading every substitution under `docker/`, deciding for each whether some tree
declares the same value, and registering the ones that do. The mechanism needs nothing new: a
module constant where a `Field(...)` call hides the number, `Form.WHOLE` where docker's own
syntax cannot take it as written, an occurrence count where several uses are one set.

Two rules are worth settling in the same pass, since the survey applies them dozens of times. Which
restatements outside `docker/` count: a runbook row that states a shipped default counts today,
while a paragraph reasoning about the number does not, and that line was drawn on two examples. And
what to do about defaults that appear in a compose file and nowhere else, which is most of them.

## History

- 2026-08-20: Opened by the close of [R-315](315-subagent-cpu-budget-and-its-siblings.md), which
  registered the four settings it had measured and left the fifty it had not, exactly as the close
  of [R-306](306-subagent-memory-budget-spelled-twice.md) and the salience limit's close before it.
- 2026-08-21: Done as the survey itself. The number is 70 substitutions over 56 distinct variables,
  not "around fifty"; one variable has two defaults on purpose, the subagent memory budget's `8.0`
  and `8`. They sort into 43 that restate a value some tree declares and 13 that name a path, a
  model file, an endpoint, a container limit or a password nothing else declares. Of the 43, ten
  were already registered, twenty are registered now (nineteen registry entries covering twenty six
  uses, with eleven numbers moved out of `Field(...)` calls into module constants and three compose
  defaults rewritten to match the decimals their constants declare), and thirteen are declarations
  the reducer cannot compare: eight empty sentinels that state no value at all, three booleans and
  two signed integers. Every registration was proved able to fail, twenty six planted differences,
  each reverted and compared byte for byte. Both rules are settled in ADR-0042: a restatement
  outside `docker/` counts when the value moving makes it wrong and not when it makes it history,
  and a default that appears only in compose files is not a pair, since a scan over it would assert
  that a file agrees with itself. The registry split twice more under the line cap, into
  `scripts/subagentcouplings.py` and `scripts/modelhostcouplings.py`, and `scripts/registry.py` now
  names the parts so the next split never touches the scan. Four narrower tasks open:
  [R-354](354-two-declared-defaults-the-reducer-refuses.md),
  [R-355](355-one-variable-several-defaults-no-declaration.md),
  [R-356](356-the-body-port-is-a-bare-literal.md) and
  [R-377](377-a-comment-restates-a-registered-value.md), the last for the comments above the
  substitutions, which this pass did not read and two of which quote a number it went on to
  register.
