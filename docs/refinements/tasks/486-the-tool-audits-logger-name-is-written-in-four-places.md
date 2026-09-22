# The tool audit's logger name is written in four places and checked nowhere

**Status:** done 2026-08-28
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`cortex.tools.audit` is written in `brain/packages/tools/src/cortex_tools/audit.py` as the argument
of the `logging.getLogger` call, and restated in three more places: the docstring of
`brain/packages/orchestrator/src/cortex_orchestrator/config_logging.py`, which names it to say which
trails log at INFO; [tools-mcp.md](../../runbooks/tools-mcp.md), which says one such line is written
per call; and [local-dev-wsl.md](../../runbooks/local-dev-wsl.md), which names it beside the recall
trail. That last sentence names one logger the registry covers and one it does not, in the same
clause. The trail itself is [ADR-0009](../../adr/ADR-0009-tools-mcp.md)'s.

The fix is the shape the recall trail took: a private `_LOGGER_NAME` in the sink, one entry in
`scripts/trailcouplings.py`, and the three restatements compared with it.

## History

- 2026-08-28: opened by the close of
  [R-469](469-the-trails-logger-name-is-written-in-three-places.md), whose close
  names this as the asymmetry it creates: the recall trail's logger is compared with the three
  documents that restate it and its sibling's with nothing.
- 2026-08-28: closed, as [ADR-0045](../../adr/ADR-0045-documented-log-lines.md) decision 13 and a
  fourth entry in `scripts/trailcouplings.py`, which now covers both per-line trails. The sink
  declares `_LOGGER_NAME` and the four restatements are compared with it. This entry undercounted by
  one: `brain/packages/orchestrator/tests/test_config_logging.py` is a fifth place, writing a record
  under the literal name and asserting the rendered line back, because what it tests is what a line
  looks like once it leaves the process. It renames with itself, both copies moving together, so it
  does not fail for exactly the mutation this entry was filed for, and it is registered as two
  search texts rather than one counted twice. The question this entry asked, whether the sibling
  module's docstring should be registered, was settled by registering it: the docstring's claim is
  an argument about levels and its suite is the proof, and neither is an instruction to select a
  stream, but the registry covers places that restate a value rather than claims of one kind, and a
  rename would leave the argument about a logger nothing writes. What the registry cannot cover is
  recorded beside the entry: that same sentence names the recall trail in prose rather than by its
  logger. The module contract for the tools package gained a sentence about the declaration and
  deliberately not the name. Opened by this close:
  [R-487](487-the-tool-audits-message-is-written-in-three-places.md) and
  [R-488](488-a-declared-logger-name-is-never-held-to-the-call-that-passes-it.md), which a mutation
  written to be a failing row found by measuring zero.
