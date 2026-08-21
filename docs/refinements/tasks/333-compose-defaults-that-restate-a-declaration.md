# Which compose defaults restate a declaration has never been surveyed

**Status:** landed 2026-08-21
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-20 by the close of [R-315](315-subagent-cpu-budget-and-its-siblings.md), which is the
third close in a row to decline the same question in the same words. The constant scan reaches a
compose default now, and eight entries use that reach: the salience limit, the two brain-to-body
deadlines, the log rendering, and the five subagent knobs. Every one of them was found by reading
the file somebody happened to be editing, which is not a survey and does not claim to be.

**What is unmeasured.** Around fifty `${CORTEX_*:-default}` substitutions live under `docker/`. Most
name a path, a model file, a port, or a host-shaped number that no Python constant declares, and
those are not couplings at all: there is nothing on the other side to disagree with. Some restate a
default the brain or the body declares, and each of those is the drift the scan exists to report,
sitting untied. Nobody has read the fifty and sorted them into the two piles, so the count of
untied restatements is unknown rather than small.

**What would close it.** Read every substitution under `docker/`, decide for each whether some tree
declares the same value, and register the ones that do. The mechanism is finished and needs nothing
new: a module constant where a `Field(...)` call hides the number, `Spelling.WHOLE` where docker's
own syntax cannot take it as written, an occurrence count where several spends are one set. What the
work costs is the reading, and what it buys is knowing the number rather than assuming it.

Two things are worth settling in the same pass, since they are the rules the survey will apply
dozens of times. The first is which restatements outside `docker/` count: a runbook row that states
a shipped default is a far side today, while a paragraph reasoning about the number with it is
deliberately not, and that line was drawn on two examples rather than on a survey. The second is
what to do about the defaults that appear in a compose file and nowhere else, which is most of them:
they are uncoupled by construction and a scan that registered them would be asserting that a file
agrees with itself.

## Trail

- 2026-08-20: opened by the close of [R-315](315-subagent-cpu-budget-and-its-siblings.md), which
  tied the four knobs it had measured and left the fifty it had not, exactly as the close of
  [R-306](306-subagent-memory-budget-spelled-twice.md) and the salience limit's close before it.
- 2026-08-21: landed as the survey itself. **The number is 70 substitutions spelling 56 distinct
  variables**, not "around fifty"; one variable carries two defaults on purpose, the subagent
  memory budget's `8.0` and `8`. They sort into 43 that restate a value some tree declares and 13
  that name a path, a model file, an endpoint, a container limit or a password nothing else
  declares. Of the 43, ten were already tied, **twenty are tied now** (nineteen registry entries
  covering twenty six spends, with eleven numbers hoisted out of `Field(...)` calls into module
  constants and three compose defaults re-spelled to match the decimals their constants declare),
  and thirteen are declarations the reducer cannot compare: eight empty sentinels that state no
  value at all, three booleans and two signed integers. Every registration was proved able to
  redden, twenty six planted drifts, each reverted and compared byte for byte. Both rules the
  survey needed are settled in the ADR-0029 compose-default survey addendum: a restatement outside
  `docker/` is a far side when the value moving makes it **wrong** and not when it makes it
  **history**, and a default that appears only in compose files is **not** a coupling, since a
  scan over it would assert that a file agrees with itself. The registry split twice more under
  the line cap, into `scripts/subagentcouplings.py` and `scripts/modelhostcouplings.py`, and
  `scripts/registry.py` now names the parts so the next split never touches the scan. Four
  narrower tasks open: [R-354](354-two-declared-defaults-the-reducer-refuses.md),
  [R-355](355-one-variable-several-defaults-no-declaration.md),
  [R-356](356-the-body-port-is-a-bare-literal.md) and
  [R-377](377-a-comment-restates-a-registered-value.md), the last for the comments above the
  substitutions, which this pass did not read and two of which quote a number it went on to
  register.
