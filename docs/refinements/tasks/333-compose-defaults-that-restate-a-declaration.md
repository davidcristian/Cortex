# Which compose defaults restate a declaration has never been surveyed

**Status:** open, actionable
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
