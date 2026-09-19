# The swap path never names the conversation, so a chat's evidence stops at the handoff

**Status:** done 2026-08-25
**Area:** inference-model-manager
**Origin:** [ADR-0046](../../adr/ADR-0046-work-identities-on-log-lines.md)

Seven other modules attach `session_id` to a line and the tool audit sink writes it on every call
it records, and the memory runbook tells an operator to grep it. The swap path attached none: the
conductor's four refusals, the settler's three, boot recovery's stranded record and the deep
phase's two cadence lines all named the turn and stopped there. So `grep session_id=s-...` returns
a chat's recalls, its rank fallbacks, its mid-turn failures, its summaries and every tool call it
made, and returns nothing about the handoff that chat asked for, which is the most expensive thing
that happens in it. The turn id joins the two halves only if the reader already has it, and the
reader grepping by conversation is exactly the reader who does not.

The conversation is already in scope at six of the eleven, which makes those six cheap:
`run_handoff` and `_prepare` are both handed `session_id`, and the settler's `fail` and boot
recovery each hold a record with `HandoffRecord.session_id`. The other five would need it passed
down, so the question there is whether to pass the record or to leave those lines naming the turn
alone. The decision is per line rather than per module: a refusal and a settle are about a turn
somebody is waiting on, and the deep tier's decode rate is about the machine.

## History

- 2026-08-24: opened by the close of
  [R-415](415-the-swap-path-names-its-work-with-bare-nouns.md), whose per-record read of the whole
  swap path found the missing field. Filed against ADR-0046.
- 2026-08-25: closed as ADR-0046 decision 6. All eleven records now name the conversation beside
  the turn, including the cadence lines this entry doubted, and the rule is written in the swap
  runbook: a line about one handoff names both ids, a line about the card names neither. Boot
  recovery's residency lines are that contrast in code and were left as they are. The entry's
  reading of the tree was right, which is unusual for this backlog: eleven records across four
  modules, six with the conversation already in scope and five needing it passed down, which is
  exactly the three private settler writes and `_report_cadence`. Those four now take the
  `HandoffRecord` that every caller already held rather than a bare id. The cadence question was
  decided the way the entry leaned against, for a reason it did not have: every other swap-path
  line is a failure path, so the cadence report is the only record a handoff that worked ever
  writes, and leaving it alone would have left a successful slow handoff unreachable from the chat.
  The field-count worry was checked rather than assumed and is not a constraint, the rendered-value
  bound being about characters in one value. One defect turned up while editing the runbook's
  verbatim sample, unrelated to this entry: it printed the fields in call-site order where the
  formatter prints them in name order, so the line it showed was one no container ever emits. Fixed
  here, and the class filed as
  [R-435](435-a-runbook-prints-a-log-line-the-formatter-never-renders.md).
