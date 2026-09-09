# Nothing says which log lines a runbook should print

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-09
**Trigger:** a line somebody wanted during a real failure, and no runbook named, is written down in
this file's Trail. That is the evidence the entry says nobody has collected, and it is what decides
between the two closes below: a gated criterion needs at least one such line to be written against,
and the editorial close needs none. The trigger fires when a Trail bullet here names one, which is
checkable by reading this file.

Opened 2026-08-26 by the close of
[R-438](438-a-documented-log-sample-can-still-print-the-wrong-fields.md), which built the scan that
holds a documented log sample to the call that writes it and, in doing so, answered only half of
the question a reader has about those samples.

`scripts/samplecheck.py` holds every sample it finds, and it finds them by walking
`docs/runbooks/`. That makes agreement automatic: a sample cannot go on printing a field the code
stopped attaching. It says nothing at all about **coverage**. A line the brain writes and no
runbook mentions is invisible to that scan by construction, because a scan over what a document
prints can only ever be as complete as the document. The brain writes far more lines than the
thirteen the runbooks print, and which of them an operator would want documented is a question
nobody has asked in one place.

The two questions are genuinely different and the second is much harder. Agreement is decidable: a
sample either matches its call site or it does not. Coverage is a judgement about which lines are
worth an operator's attention, and the obvious mechanical answers are all wrong. Requiring every
`_logger` call to appear in a runbook would document hundreds of lines nobody reads and turn the
runbooks into a log catalogue. Requiring every `WARNING` and above would be closer and still wrong,
since the levels are a statement about the machine rather than about what a reader needs.

**Why it was left.** The close it came out of was about a sample that disagrees with the code, and it
built the scan that catches one. Adding a coverage rule to the same scan would have meant inventing the
criterion in the same commit as the mechanism, with no evidence about which lines are actually
missed. The evidence that would settle it is the cheap kind to collect and nobody has collected
it: a note, each time somebody goes to the logs during a real failure, of which line they wanted
and whether a runbook named it.

**What would close it.** Either a written criterion for which lines a runbook owes an operator,
with a scan holding the brain's calls to it, or a written argument that the runbooks are prose
about diagnosis rather than a catalogue of lines and that coverage is therefore an editorial
question rather than a gated one.

**One line has since been answered by precedent, which is neither close.** On 2026-09-08 a warning
was added to `SubagentRunner` for a spawn the scheduler refuses, and the same commit printed the
rendered line in `docs/runbooks/subagents-cpu.md`. Three deferred entries had asked to observe a
refusal and could not, and the reason was not that a runbook named no line: the brain wrote no
line at all, the refusal reaching only a cortex reply nothing keeps, a Redis record that expires,
and a tool audit line carrying the batch's size rather than its text. So the want was met by
writing the line and documenting it in one change, and the criterion applied was that this line is
the only durable record of the event. That is the nearest thing to the evidence this entry asks
for, and it is evidence about a line the brain did not write rather than about one no runbook
names.

## Trail

- 2026-08-26: opened by the close of
  [R-438](438-a-documented-log-sample-can-still-print-the-wrong-fields.md), which built the
  agreement half of the question. Recorded under what the ADR-0009 sample-membership addendum
  defers.
- 2026-08-29: sharpened by the close of
  [R-487](487-the-tool-audits-message-is-spelled-in-three-places-and-held-in-none.md), which tried
  a rendered sample of the tool audit trail on the committed tree and had it refused. Some of the
  brain's lines cannot be documented as held samples at all: `LoggingAuditSink` builds its `extra=`
  across statements and by condition, so `logcalls.py` reports a call it cannot read a field list
  off, and there is no single field list such a line could print. So a criterion for which lines a
  runbook owes an operator has a second half nobody had noticed, which lines the mechanism can
  hold, and the fault a writer meets today names the sink rather than saying the line is
  unsampleable.
- 2026-09-07: checked, narrowed and left open. The trigger has not fired, and the clause it fired
  on could not have: "an operator goes to the logs during a real failure, wants a line, and finds
  that no runbook names it" is an event outside the tree, so no state of the repo makes it true or
  false and a reader checking this entry had nothing to read. It is narrowed above to the same
  evidence written down here, which a reader can check by reading this file. No such line is
  recorded, so the entry stays open on the choice between its two closes rather than on evidence.

  Two readings were taken while checking, and both move the body's numbers.
  `scripts/samplecheck.py` now reports 12 samples across 12 runbooks, resolved against 38 loggers
  the brain declares and the 93 messages it logs, where this entry was written when the runbooks
  printed three. So the runbooks print four times as many lines as they did and still print an
  eighth of what the brain writes, and the body above is updated to say twelve. The second half the
  2026-08-29 bullet above named is answered: `_proven` in `samplecheck.py` and `assertedlines.py`
  land a sample of a call whose field list the source cannot read on a line the sink's own suite
  asserts whole, so five of the twelve samples are held that way and the tool audit trail is
  documentable after all. What remains unanswered is only the first half, which lines a runbook
  owes an operator.
- 2026-09-09: verified against the code, one number repaired and one paragraph added. The trigger
  has not fired: no Trail bullet here names a line somebody wanted and no runbook had. Both counts
  in the body had moved in two days. `scripts/samplecheck.py` reports 13 samples across the same
  12 runbooks, resolved against the same 38 loggers and 94 messages rather than 93, because the
  refusal warning added on 2026-09-08 wrote a new message and printed it in
  `docs/runbooks/subagents-cpu.md`. Five samples are still held to a line the sink's own suite
  asserts whole. That commit is the paragraph added above: it is the first time somebody wanted an
  event out of the logs and acted on it, and what it says about the criterion is that the answer
  can be to write the line rather than to document one.
