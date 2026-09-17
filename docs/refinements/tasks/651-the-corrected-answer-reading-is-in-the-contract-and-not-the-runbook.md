# The corrected-answer reading is in the contract and not in the runbook

**Status:** landed 2026-09-17
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-09-12 by the close of
[591](591-an-ok-audit-line-carries-a-size-where-the-correction-is.md), which decided that the audit
trail keeps a successful call's size and wrote down what `trust` recovers instead.

That close put the rule in `docs/modules/brain-tools.md`, beside the sink's contract, because that
is where what the sink writes and why is stated. The document an operator opens while something is
broken is `docs/runbooks/tools-mcp.md`, which prints the five shapes of the line and explains the
tool name, the arguments, the `trust` provenance, the timestamp, `result_chars`, `error` and the
four work ids, and says nothing about `trust=trusted` on an `ok` line being the brain's own
sentence. So an operator working back from a turn that ended badly can be told, by the runbook,
every field on the line and not the one reading that recovers what a tool answered.

Whether the runbook owes that sentence is the coverage question
[R-444](444-nothing-says-which-log-lines-a-runbook-should-print.md) holds open, one line at a time
rather than in general: a runbook is prose about diagnosis, and a rule restated in two documents
that no gate ties drifts, since the registry parts naming either document tie constants in it
rather than its prose. Against that, this is the one reading that turns a size back into an answer,
and it is three fields wide.

**What would close it.** Either a sentence in the tools runbook naming the filter, `ok=True` with
`trust=trusted` under a tool the own-text set declares, taken as one instance of the coverage
question rather than as a rule about runbooks generally; or a recorded decision that the reading
belongs to the sink's contract alone, because it is a statement about how the trail is built rather
than a step in diagnosing a turn.

## Trail

- 2026-09-12: opened by the close of
  [591](591-an-ok-audit-line-carries-a-size-where-the-correction-is.md), which wrote the rule down
  for a future agent and left the operator's document alone.
- 2026-09-17: landed as one sentence in the tools runbook, and the premise was narrower than
  written. The trigger had not fired: `cortex_orchestrator/own_texts.py` still declares five
  entries over four texts, and the sidecar still marks three of them `isError` (the refused search
  and the unknown folder under both tools) and answers two `ok`, the empty search and the
  not-found uid; the refused-search change of 2026-09-15 sends a refused search on an empty folder
  to the existing empty-search answer and declares nothing new. But the runbook was not silent: its
  paragraph on `trust=trusted` beside `ok=False`, written on 2026-09-02 and so ten days before this
  entry, already listed all four answers, said each is re-stamped trusted, and said the first two
  arrive failed, so the `ok` reading was implied there and never stated. That paragraph now says
  which answer an `ok=True`, `trust=trusted` line is under each tool and that the line's own
  `arguments` render it, and that the file trail added the same day keeps those fields. It is one
  instance of the coverage question
  [R-444](444-nothing-says-which-log-lines-a-runbook-should-print.md) holds open, and it adds no
  second statement of the set, since the paragraph already named its members. Recorded in the
  ADR-0009 corrected-answer-runbook addendum.
