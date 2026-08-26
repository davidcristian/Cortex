# Nothing says which log lines a runbook should print

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** An operator goes to the logs during a real failure, wants a line, and finds that no
runbook names it.

Opened 2026-08-26 by the close of
[R-438](438-a-documented-log-sample-can-still-print-the-wrong-fields.md), which built the scan that
holds a documented log sample to the call that writes it and, in doing so, answered only half of
the question a reader has about those samples.

`scripts/samplecheck.py` holds every sample it finds, and it finds them by walking
`docs/runbooks/`. That makes agreement automatic: a sample cannot go on printing a field the code
stopped attaching. It says nothing at all about **coverage**. A line the brain writes and no
runbook mentions is invisible to that scan by construction, because a scan over what a document
prints can only ever be as complete as the document. The brain writes far more lines than the
three the runbooks print, and which of them an operator would want documented is a question nobody
has asked in one place.

The two questions are genuinely different and the second is much harder. Agreement is decidable: a
sample either matches its call site or it does not. Coverage is a judgement about which lines are
worth an operator's attention, and the obvious mechanical answers are all wrong. Requiring every
`_logger` call to appear in a runbook would document hundreds of lines nobody reads and turn the
runbooks into a log catalogue. Requiring every `WARNING` and above would be closer and still wrong,
since the levels are a statement about the machine rather than about what a reader needs.

**Why it was left.** The close it came out of was about a sample that lies, and it built the scan
that stops one lying. Adding a coverage rule to the same scan would have meant inventing the
criterion in the same commit as the mechanism, with no evidence about which lines are actually
missed. The evidence that would settle it is the cheap kind to collect and nobody has collected
it: a note, each time somebody goes to the logs during a real failure, of which line they wanted
and whether a runbook named it.

**What would close it.** Either a written criterion for which lines a runbook owes an operator,
with a scan holding the brain's calls to it, or a written argument that the runbooks are prose
about diagnosis rather than a catalogue of lines and that coverage is therefore an editorial
question rather than a gated one.

## Trail

- 2026-08-26: opened by the close of
  [R-438](438-a-documented-log-sample-can-still-print-the-wrong-fields.md), which built the
  agreement half of the question. Recorded under what the ADR-0009 sample-membership addendum
  defers.
