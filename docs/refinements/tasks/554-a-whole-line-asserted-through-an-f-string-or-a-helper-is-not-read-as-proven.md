# A whole line asserted through an f-string or a helper is not read as asserted

**Status:** declined 2026-10-16
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`scripts/assertedlines.py` reads a string only where it is one side of `assert x == "..."`, as a
constant the parser has already joined from adjacent literals. `_equated` inspects both sides of the
equality and `_rendered` accepts whichever one is a one-line string constant, so the side holding
the produced line may be a name: the audit suite's schedule-fire assertion binds it to `line` above
the assert and is read. It is the expected side that has to be a constant, which is how every
whole-line assertion in that suite is written today. A suite that moved its expected line into an
f-string, to interpolate `_AT.isoformat()` rather than write the date twice, or into a helper that
renders the line from the fields, would leave every runbook sample of that sink unchecked. The check
fails rather than passes, which is the right direction, but it reports the failure at the runbook,
`docs/runbooks/tools-mcp.md` and the sample's own line, for a change made in the suite. It does name
the suite directory and list what is asserted whole there, which reads `none` once every assertion
has moved into an f-string.

Closing it: an f-string whose parts are constants and expressions could be read as the constant
parts with a hole where each expression stands, and matched against a sample by field name, since
values are dropped anyway. A helper cannot be read without running it. Declined on 2026-10-16
(History): the one such assertion of a call the field reader refuses puts its expressions at the
logger and the message, where that reading has nothing to match, and a sample of that line fails
`just check` the day it is written, naming the call and the suite. The fix then belongs in the call,
whose fields can be bound to a mapping written out, or in the suite, as a constant line.

## History

- 2026-09-05: opened by the close of
  [R-523](523-the-tool-audit-line-is-described-in-prose-because-its-fields-vary-by-condition.md),
  whose reader's suite records the f-string as left unread and says nothing about reading it.
- 2026-09-12: checked against the code, with the trigger narrowed and two claims repaired. The
  trigger has not fired: every `assert` in `brain/packages/tools/tests/test_audit.py` whose test is
  one `==` and which produces a line opening with a level has a string constant on one side, and
  `assertedlines.proven` returns all six. Only the expected side has to be a constant, since
  `_equated` reads both sides, so the clause that made a bound name count is corrected. And the
  failure does point at the suite, naming the directory and listing the field lists asserted whole
  there; what misleads is the runbook anchor rather than the words. One property was checked because
  a sibling review found the constant registry matching a search text against a whole file rather
  than one line: this reader has the opposite form, since `SAMPLE.match` is anchored at the start of
  one string constant, a constant containing a newline is refused by `_rendered`, and the document
  side reads one markdown line at a time.
- 2026-09-14: checked again with nothing repaired. The trigger has not fired. All fifteen
  single-`==` asserts in `test_audit.py` were read: ten have a one-line string constant on a side
  and five do not, and none of those five would produce a line opening with a level.
  `assertedlines.proven` returns the same six lines. One thing derived while checking:
  `samplecheck.disagreement` sends every call whose field list the source cannot read to `_proven`,
  not only the audit sink's, so the reader is consulted for the four call-shaped refusals
  [R-619](619-four-refusal-lines-attach-their-fields-by-a-call.md) is about. No runbook prints one
  of those four today.
- 2026-09-15: checked again, with the trigger narrowed, the reason for leaving it weakened and its
  reach widened. The trigger as written fired on the form existing anywhere, and it now exists:
  `brain/packages/core/tests/test_log_format.py:336` asserts a whole line through an f-string,
  `f"INFO:cortex.test:hello api_key={REDACTED}"`. Nothing is left unchecked by it, since the logger
  is `cortex.test`, which no module under the brain declares, so a sample of that line fails at the
  logger before the suite is read. The trigger is narrowed to a line whose logger a brain module
  declares. Reach widened: `docs/runbooks/model-swap.md` now prints the refusal line of
  `cortex_orchestrator/swap_builders.py`, checked against a whole line `test_swap_wiring.py`
  asserts, so this reader is required for two package suites rather than one.
- 2026-09-19: checked again, and the trigger as narrowed on 2026-09-15 had already fired the day it
  was written. `brain/packages/orchestrator/tests` is a suite this reader is consulted over, and it
  asserts three whole lines through f-strings, `test_abandon.py:485` for
  `cortex_orchestrator.abandon` and `test_converse.py:530` and `:592` for
  `cortex_orchestrator.converse_stream`, all from 2026-08-19 and 2026-08-20. Both loggers are
  declared by brain modules, so the clause held and the previous reading was wrong. Nothing is left
  unchecked by them, because those calls' field lists are read off the calls and `_proven` is
  reached only for a call the reader cannot read. So the trigger is narrowed again, to a line of
  such a call, and those calls are counted: the tool audit, the swap refusal, the two bounds
  refusals and the residency watch's worst-stop line. Of those only the first two are asserted whole
  in any form. The core suite gained a second `cortex.test` f-string on 2026-09-17 at
  `test_log_format.py:334`, and the one cited above has moved to line 415. `test_audit.py` still
  writes fifteen single-`==` asserts, ten with a one-line string constant; the orchestrator's suite
  now writes 558.
- 2026-10-02: checked again, with the count and one reason corrected. The trigger has not fired.
  The reader cannot read six calls in five modules now: on 2026-09-25 the recall sink began
  attaching `recall_fields(audit)`, and `brain/packages/memory/tests` asserts no whole line in any
  form. Across the four suites consulted, no single-`==` assert without a one-line string constant
  would produce one of the six calls' lines. The body said every f-string whole line interpolates
  its logger; `test_log_format.py:229` and `:280` and `test_device_memory.py:89` write it out.
- 2026-10-16: the trigger fired. On 2026-10-10 the commit that ends a turn cut by a brain
  shutdown with a typed error moved the stream's turn failure lines in `converse_stream.py` to
  `extra=fields`, a parameter, so the field reader cannot read them: it now refuses eleven calls in
  six modules, against six in five on 2026-10-02, five of the eleven in that module. And
  `test_a_turn_that_failed_names_the_session_and_the_turn_it_was_serving` in
  `orchestrator/tests/test_converse.py` asserts three of those lines whole through the f-string
  `f"ERROR:{_STREAM_LOGGER}:{message} session_id=s7 turn_id=t-1"`. No runbook prints any of the
  three yet. The trigger line is gone and the task is actionable.
- 2026-10-16: declined. The field reader refuses eleven calls in six modules, and no runbook
  prints a line of any of them except the tool audit and the swap refusal, both asserted as
  constants; `samplecheck.py` passes 19 samples, 6 held to a suite line. The f-string that fired
  has its expressions at the logger, `_STREAM_LOGGER`, and the message, a `parametrize` argument,
  so the planned reading would not read it either. A sample of `inference failed mid-turn`
  appended to a `git archive` copy's `docs/runbooks/model-swap.md` failed with exit 1, naming
  `converse_stream.py:228`, its reason and the orchestrator suite (`asserted whole there: none`).
  In that copy, binding `fields` to a mapping written out at the top of `_turn_task` made the same
  sample pass against the call itself, and one with a field added fail, with the reader unchanged.
  So the reader stays as it is; a runbook that needs one of these lines makes its call readable.
