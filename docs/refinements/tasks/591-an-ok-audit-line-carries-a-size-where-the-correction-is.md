# An ok audit line records a size where the correction is

**Status:** done 2026-09-12
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`LoggingAuditSink.record` writes `error` with the result detail when `invocation.ok` is false and
`result_chars` with the length alone when it is true
(`brain/packages/tools/src/cortex_tools/audit.py`). The reason is stated where it is written and
still holds: a successful file read can be large or sensitive, and the trail is not the place for
its content. The consequence is that an answer which corrected the model and is recorded `ok` leaves
nothing of that correction on the line. `read_email`'s not-found answer is one such answer by
decision, and `search_emails` answering no matches is another. So an operator working back from a
turn that ended badly sees a character count on the read that told the model to search again.

## History

- 2026-09-06: opened by the close of
  [582](582-the-not-found-answer-is-the-one-correction-the-audit-records-as-ok.md), which recorded
  what a reading over `ok` counts and left what an `ok` line records alone.
- 2026-09-12: done as an editorial close, after a check that overturned the entry's central claim.
  An `ok` line does record something of the correction, and it is not `result_chars`.
  `build_tool_registry` puts `OwnTextToolRegistry` outermost over the shared root and
  `ToolDispatcher._audited` records the trust off the result the chain returned, so the `trust` on
  the line is the overlay's byte comparison against a sentence the brain holds. Three of the five
  own texts are answered `isError` and reach the trail `ok=False` with their whole text under
  `error`; the two recorded `ok` are `read_email`'s not-found answer and `search_emails`'s empty
  search. So `ok=True` with `trust=trusted` under either tool's name is exactly one of the two
  corrections, and the `arguments` on the same line are what its text is built from, which makes
  both recoverable from one line. The decision is that the trail keeps the size: a bounded first
  line of the content would put part of every file read on the trail to serve the few answers that
  correct the model; a flag a sidecar declares beside its answer would be the sidecar's word about
  itself where the byte comparison is the brain's own; and a count matched against the own-text
  registry is a reading over the trail rather than a change to it. `docs/modules/brain-tools.md` now
  states what logging the size costs, that nowhere durable holds the text either since the tool
  loop's `Role.TOOL` results reach a store only inside an escalating turn's handoff record, and what
  `trust` recovers. `docs/modules/brain-email.md` is corrected on the same point. ADR-0009 decision
  16 has the reasoning; no code moved. What this leaves is
  [651](651-the-corrected-answer-reading-is-in-the-contract-and-not-the-runbook.md): the rule is
  written in the sink's contract, and the tools runbook, which is what an operator opens while
  something is broken, explains every field except the one reading that turns a size back into an
  answer.
