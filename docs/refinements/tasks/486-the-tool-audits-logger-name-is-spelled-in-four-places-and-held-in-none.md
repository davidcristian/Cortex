# The tool audit's logger name is spelled in four places and held in none

**Status:** landed 2026-08-28
**Area:** repo-gates
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-28 by the close of
[R-469](469-the-trails-logger-name-is-spelled-in-three-places-and-held-in-none.md), which built the
mechanism for the sibling trail and deliberately applied it to one of the two.

The trail itself is [ADR-0009](../../adr/ADR-0009-tools-mcp.md)'s, and its name is
unheld the way its sibling's was.

`cortex.tools.audit` is written in `brain/packages/tools/src/cortex_tools/audit.py`, as the
argument of the `logging.getLogger` call, and restated in three more places: the docstring of
`brain/packages/orchestrator/src/cortex_orchestrator/config_logging.py`, which names it to say
which trails log at INFO and therefore what the shipped level admits;
[tools-mcp.md](../../runbooks/tools-mcp.md), which says one such line is written per call; and
[local-dev-wsl.md](../../runbooks/local-dev-wsl.md), which names it beside the recall trail as one
of the two per-line trails worth knowing about. That last sentence now names one logger the
registry holds and one it does not, in the same clause.

**What would close it.** The same shape the recall trail took: a private `_LOGGER_NAME` in the
sink, one entry in `scripts/trailcouplings.py` or a part beside it, and the three restatements as
mentions. `scripts/logcalls.py` already resolves a logger named through a module constant, so
nothing in the gate tree has to change; the audit sink's own suite pins the name the way the
memory package's does, so the rename is loud in code and silent in the documents, which is the
asymmetry the recall trail's entry measured.

**One question to settle first**, and it is the reason this is not a copy of the entry it came
from. Three of the four places are the trail's own instructions and one is a sibling module's
docstring, which is a far side the registry reaches but a different kind of claim: it is an
argument about log levels that happens to name this logger, not an instruction to select by it.
Register it as a mention like the rest, or leave it and say why, but say which.

## Trail

- 2026-08-28: opened by the close of
  [R-469](469-the-trails-logger-name-is-spelled-in-three-places-and-held-in-none.md), whose
  addendum names this as the asymmetry that close creates: the recall trail's logger is held to
  the three documents that restate it and its sibling's is held by nothing.
- 2026-08-28: **landed**, as the [ADR-0009 audit-logger
  addendum](../../adr/ADR-0009-tools-mcp.md) and a fourth entry in `scripts/trailcouplings.py`,
  which is now the couplings around both per-line trails rather than the recall trail's alone. The
  sink declares `_LOGGER_NAME` and the four restatements are mentions. **This entry undercounted by
  one**: `brain/packages/orchestrator/tests/test_config_logging.py` is a fifth place, writing a
  record under the literal name and asserting the rendered line back, because what it tests is what
  a line looks like once it leaves the process. It renames with itself, both spellings moving
  together, so it is silent for exactly the mutation this entry was filed for, and it is registered
  as two needles rather than one counted twice. **The question this entry asked was settled by
  registering.** The docstring's claim is an argument about levels and its suite is the proof of
  that argument, and neither is an instruction to select a stream, but the registry holds places
  that restate a value rather than claims of one kind, and a rename leaves the argument about a
  logger nothing writes and the proof demonstrating it on an abandoned name. What the registry
  cannot hold is recorded beside the entry: that same sentence names the recall trail in prose
  rather than by its logger, so it is tied to one of the two loggers it is about. The module
  contract for the tools package gained a sentence about the declaration and deliberately not the
  name, a fifth restatement written in order to be gated being the gate choosing its own subject.
  Opened by this close:
  [R-487](487-the-tool-audits-message-is-spelled-in-three-places-and-held-in-none.md) for the
  message beside this name on the same line, and
  [R-488](488-a-declared-logger-name-is-never-held-to-the-call-that-passes-it.md), which a mutation
  written to be a red row found by measuring zero: the registry holds the declaration and never
  asks that the sink's own call passes it.
