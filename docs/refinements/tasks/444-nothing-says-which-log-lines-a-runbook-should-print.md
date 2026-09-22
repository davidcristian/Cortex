# Nothing says which log lines a runbook should print

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)
**Verified:** 2026-09-19
**Trigger:** a line somebody wanted during a real failure, and no runbook named, is written down in
this file's History section. That is the evidence this entry says nobody has collected, and it is
what decides between the two closes below: a criterion a check enforces needs at least one such
line to be written against, and the editorial close needs none. The trigger fires when a History
entry here names one, which a reader can check by reading this file.

`scripts/samplecheck.py` compares every sample it finds with the call that writes it, and it finds
them by walking `docs/runbooks/`. That makes agreement automatic: a sample cannot go on printing a
field the code stopped attaching. It says nothing about coverage. A line the brain writes and no
runbook mentions is invisible to that scan, because a scan over what a document prints can only be
as complete as the document. The brain writes far more lines than the seventeen the runbooks print,
and which of them an operator would want documented is a question nobody has asked in one place.

The two questions are different and the second is harder. Agreement is decidable: a sample either
matches its call site or it does not. Coverage is a judgement about which lines are worth an
operator's attention, and the obvious mechanical answers are wrong. Requiring every `_logger` call
to appear in a runbook would document hundreds of lines nobody reads. Requiring every `WARNING` and
above would be closer and still wrong, since the levels are a statement about the machine rather
than about what a reader needs.

Either a written criterion for which lines a runbook owes an operator, with a scan comparing the
brain's calls with it, or a written argument that the runbooks are prose about diagnosis rather
than a catalogue of lines and that coverage is therefore an editorial question.

One line has been answered by precedent, which is neither close. On 2026-09-08 a warning was added
to `SubagentRunner` for a spawn the scheduler refuses, and the same commit printed the rendered
line in `docs/runbooks/subagents-cpu.md`. Three deferred entries had asked to observe a refusal and
could not, and the reason was not that a runbook named no line: the brain wrote no line at all. So
the want was met by writing the line and documenting it in one change, and the criterion applied
was that this line is the only durable record of the event. On 2026-09-17 the same thing happened
again for a different reason: the output guardrail removed links without writing any line, so
nothing could count how many links the lookalike rule removed beyond the default's, and the commit
that added a line with a count printed it in `docs/runbooks/local-dev-wsl.md`.

## History

- 2026-08-26: opened by the close of
  [R-438](438-a-documented-log-sample-can-still-print-the-wrong-fields.md), which built the
  agreement half of the question. Filed against ADR-0045.
- 2026-08-29: sharpened by the close of
  [R-487](487-the-tool-audits-message-is-written-in-three-places.md), which tried
  a rendered sample of the tool audit trail on the committed tree and had it refused. Some of the
  brain's lines cannot be documented as checked samples at all: `LoggingAuditSink` builds its
  `extra=` across statements and by condition, so `logcalls.py` reports a call it cannot read a
  field list off. So a criterion for which lines a runbook owes an operator has a second half
  nobody had noticed, which lines the mechanism can compare.
- 2026-09-07: checked, narrowed and left open. The trigger has not fired, and the wording it fired
  on could not have: "an operator goes to the logs during a real failure, wants a line, and finds
  that no runbook names it" is an event outside the tree, so no state of the repo makes it true or
  false. It is narrowed above to the same evidence written down here. Two readings were taken while
  checking. `scripts/samplecheck.py` now reports 12 samples across 12 runbooks, resolved against 38
  loggers the brain declares and the 93 messages it logs, where this entry was written when the
  runbooks printed three. The second half the previous entry named is answered: `_proven` in
  `samplecheck.py` and `assertedlines.py` compare a sample of a call whose field list the source
  cannot read with a line the sink's own suite asserts whole, so five of the twelve are covered
  that way and the tool audit trail is documentable after all.
- 2026-09-09: checked against the code, one number repaired and one paragraph added. The trigger
  has not fired. `scripts/samplecheck.py` reports 13 samples across the same 12 runbooks, against
  the same 38 loggers and 94 messages rather than 93, because the refusal warning added on
  2026-09-08 wrote a new message and printed it in `docs/runbooks/subagents-cpu.md`. Five samples
  are still covered through a suite assertion. That commit is the precedent added above.
- 2026-09-12: checked again. The trigger has not fired. `scripts/samplecheck.py` reports 14 samples
  across the same 12 runbooks, against the same 38 loggers and the 100 messages the brain logs
  rather than 94, and 5 samples are still covered through a suite assertion. The fourteenth is in
  `docs/runbooks/vision.md`, which began printing the vision probe's line on 2026-09-10. The
  runbooks still print a seventh of what the brain writes.
- 2026-09-14: checked again, and the first check since this entry was opened at which no number
  moved: the same 14 samples across the same 12 runbooks, the same 38 loggers and 100 messages,
  with 5 covered through a suite assertion.
- 2026-09-15: checked again. `scripts/samplecheck.py` reports 16 samples across the same 12
  runbooks, against the same 38 loggers and the 101 messages it logs rather than 100, and 6 of the
  samples are covered through a suite assertion rather than 5. The sixth is
  `docs/runbooks/model-swap.md` printing the refusal line of
  `cortex_orchestrator/swap_builders.py`, whose fields the source cannot list because they are what
  another call returns. The runbooks still print a sixth of what the brain writes.
- 2026-09-19: checked again. The trigger has not fired. `scripts/samplecheck.py` reports 17 samples
  across the same 12 runbooks, against 39 loggers rather than 38 and 103 messages rather than 101,
  with the same 6 covered through a suite assertion. Both moves come from two commits of
  2026-09-17. The seventeenth sample is the output guardrail's link-removal line in
  `docs/runbooks/local-dev-wsl.md`, compared with its call directly rather than through a suite,
  and is the second precedent described above. The thirty-ninth logger is `cortex_tools.audit_file`,
  whose one line, the `tool.audit.gap` warning written when an append to the audit file fails, is
  named with its `error` field in the prose of `docs/runbooks/tools-mcp.md` rather than printed as
  a sample, so no check compares that sentence with the call.
