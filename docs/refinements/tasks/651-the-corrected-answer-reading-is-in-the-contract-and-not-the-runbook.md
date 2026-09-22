# The corrected-answer reading is in the contract and not in the runbook

**Status:** done 2026-09-17
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The rule that `trust=trusted` on an `ok` audit line is the brain's own sentence rather than the
tool's was written into `docs/modules/brain-tools.md`, beside the sink's contract, because that is
where what the sink writes and why is stated. The document an operator opens while something is
broken is `docs/runbooks/tools-mcp.md`, which prints the five forms of the line and explains the
tool name, the arguments, the `trust` provenance, the timestamp, `result_chars`, `error` and the
four work ids, and said nothing about that reading. So an operator working back from a turn that
ended badly could be told every field on the line and not the one reading that recovers what a tool
answered.

Whether the runbook owes that sentence is the coverage question
[R-444](444-nothing-says-which-log-lines-a-runbook-should-print.md) holds open, one line at a time:
a runbook is prose about diagnosis, and a rule restated in two documents that no check compares goes
out of step. Against that, this is the one reading that turns a size back into an answer, and it is
three fields wide.

**What closed it.** One sentence in the tools runbook, taken as a single instance of the coverage
question rather than a rule about runbooks generally.

## History

- 2026-09-12: opened by the close of
  [591](591-an-ok-audit-line-records-a-size-where-the-correction-is.md), which decided that the
  audit trail keeps a successful call's size, wrote down what `trust` recovers instead, and left the
  operator's document alone.
- 2026-09-17: done, and the premise was narrower than written. The trigger had not fired:
  `cortex_orchestrator/own_texts.py` still declares five entries over four texts, and the sidecar
  still marks three of them `isError` (the refused search and the unknown folder under both tools)
  and answers two `ok`, the empty search and the not-found uid; the refused-search change of
  2026-09-15 sends a refused search on an empty folder to the existing empty-search answer and
  declares nothing new. But the runbook was not silent: its paragraph on `trust=trusted` beside
  `ok=False`, written on 2026-09-02, already listed all four answers, said each is re-stamped
  trusted, and said the first two arrive failed, so the `ok` reading was implied there and never
  stated. That paragraph now says which answer an `ok=True`, `trust=trusted` line is under each tool
  and that the line's own `arguments` render it, and that the file trail added the same day keeps
  those fields. It adds no second statement of the set, since the paragraph already named its
  members. Recorded in ADR-0009 decision 16.
