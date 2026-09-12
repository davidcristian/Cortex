# An ok audit line carries a size where the correction is

**Status:** landed 2026-09-12
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-09-06 by the close of
[582](582-the-not-found-answer-is-the-one-correction-the-audit-records-as-ok.md), which decided
that a call the server ran and answered empty is recorded `ok` even when its answer corrects the
model.

`LoggingAuditSink.record` writes `error` with the result detail when `invocation.ok` is false and
`result_chars` with the length alone when it is true
(`brain/packages/tools/src/cortex_tools/audit.py`). The reason is stated where it is written and
still holds: a successful file read can be large or sensitive, and the trail is not the place for
its content. The consequence is that an answer which corrected the model and is recorded `ok`
leaves nothing of that correction on the line. `read_email`'s not-found answer is one such answer
by decision, and `search_emails` answering no matches is another.

So the audit trail can be read for the calls a sidecar declined and cannot be read for the turns a
tool corrected. An operator working back from a turn that ended badly sees a character count on
the read that told the model to search again, and nothing on the line that says so.

**What would close it.** A decision on whether the trail should carry more than a size for an `ok`
answer, and if it should, the shape that does not put a file's contents in the logs: a bounded
first line, a flag the sidecar declares beside its answer, or a count of answers matched against
the own-text registry, which already holds every sentence the brain re-stamps as its own. If it
should not, a sentence in `docs/modules/brain-tools.md` saying that a corrected turn is not
readable from the trail and where it is readable instead.

## Trail

- 2026-09-06: opened by the close of
  [582](582-the-not-found-answer-is-the-one-correction-the-audit-records-as-ok.md), which
  recorded what a reading over `ok` counts and left what an `ok` line carries alone.
- 2026-09-12: landed as the editorial close named above, after a re-derivation that overturned the
  entry's central claim. An `ok` line does carry something of the correction, and it is not
  `result_chars`. `build_tool_registry` puts `OwnTextToolRegistry` outermost over the shared root
  and `ToolDispatcher._audited` records the trust off the result the chain returned, so the `trust`
  on the line is the overlay's byte comparison against a sentence the brain holds. Three of the five
  own texts are answered `isError` and reach the trail `ok=False` with their whole text under
  `error`; the two recorded `ok` are `read_email`'s not-found answer and `search_emails`'s empty
  search. So `ok=True` with `trust=trusted` under either tool's name is exactly one of the two
  corrections this entry is about, and the `arguments` on the same line are what its text is
  rendered from, which makes both reconstructible from one line. What the entry measured is true of
  a reading over `ok` alone.

  So the decision is that the trail keeps the size. A bounded first line of the content would put
  part of every file read on the trail to serve the few answers that correct the model; a flag a
  sidecar declares beside its answer would be the sidecar's word about itself where the overlay's
  byte comparison is the brain's own; and the count matched against the own-text registry is a
  reading over the trail rather than a change to it. `docs/modules/brain-tools.md` now states in the
  sink's contract what logging the size costs, that nowhere durable holds the text either since the
  tool loop's `Role.TOOL` results reach a store only inside an escalating turn's handoff record, and
  what `trust` recovers. `docs/modules/brain-email.md`'s claim that a reading over `ok` cannot
  recover the correction from the trail either is corrected to say what does. The ADR-0009
  trusted-answer addendum of this date carries the reasoning; no code moved, so there is no gate to
  mutate and the field set on the line is unchanged.

  What this leaves is
  [651](651-the-corrected-answer-reading-is-in-the-contract-and-not-the-runbook.md): the rule is
  written where the sink's contract is, and the tools runbook, which is the document an operator
  opens while something is broken, explains every field on the line except the one reading that
  turns a size back into an answer.
