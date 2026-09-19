# A whole line asserted through an f-string or a helper is not read as proven

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-19
**Trigger:** a whole-line assertion whose expected line is not a plain string constant (an
f-string, a name the expected line is bound to above the assert, or a helper that builds or
compares it) and whose logger and message are those of a call the code reader refuses the field
list of, since only such a call's samples are held through this reader. Countable in two steps:
list the refused calls by running `logcalls.logged` over every message `logcalls.messages` returns
and keeping those raising `UnreadFieldsError`, five calls in four modules on 2026-09-19; then read
the package suite beside each for an `assert` whose test is one `==`, with neither side a one-line
string constant, that would render one of those calls' logger and message. Binding the *rendered*
side to a name fires nothing, and the audit suite already writes one assertion that way. The five
f-string whole lines in the tree today fire nothing: two render through the fixture logger
`cortex.test`, and three render lines of `cortex_orchestrator.abandon` and
`cortex_orchestrator.converse_stream`, whose calls the code reader reads directly.

Opened 2026-09-05 by the close of
[R-523](523-the-tool-audit-line-is-described-in-prose-because-its-fields-vary-by-condition.md),
which taught `scripts/assertedlines.py` to read the rendered lines a suite asserts whole.

The reader reads a string only where it is one side of `assert x == "..."`, as a constant the
parser has already joined from its adjacent literals. `_equated` inspects both sides of the
equality and `_rendered` accepts whichever of them is a one-line string constant, so the side
carrying the rendered line may be a name: the audit suite's schedule-fire assertion binds it to
`line` above the assert and is read. It is the expected side that has to be a constant, which is
every whole-line assertion that suite writes today and the shape the reader was built against. A
suite that moved its expected line into an f-string, say to interpolate `_AT.isoformat()` rather
than spell the date twice, or into a helper taking the fields and rendering the line, would leave
every runbook sample of that sink unheld. The gate fails closed rather than open, which is the
right direction, and the fault it prints is anchored at the runbook, `docs/runbooks/tools-mcp.md`
and the sample's own line, for a change made in the suite. It does name the suite, `no line under
brain/packages/tools/tests is asserted whole with those fields`, and it lists what is asserted
whole there, which reads `none` once every assertion has moved into an f-string, so the pointer to
the other file is in the fault and only the anchor sends a reader to the sample first.

What a close would cost. An f-string whose parts are constants and expressions could be read as
the constant parts with a hole where each expression stands, and matched against a sample by
name, since values are dropped anyway; that is one more case in `_rendered` and a fixture per
part shape, plus a refusal for an f-string whose expression stands where a field name would, which
no reading of the source can supply. A helper cannot be read without executing it, and stays
refused. Not built, because no line anybody could document is asserted either way. Two suites
write the f-string shape, five times. `brain/packages/core/tests/test_log_format.py` asserts two
lines through the fixture logger `cortex.test`, which no module under the brain declares, so a
sample quoting either would be refused before the suite was read. The orchestrator's suite asserts
three, in `test_abandon.py` and `test_converse.py`, and those are lines of calls the code reader
reads directly, so `_proven` is never consulted for them. They do change the cost of the case.
Each interpolates the logger from a constant the test module binds, so a reading that leaves a hole
where an expression stands would refuse all three at the logger, and resolving the test module's
own bindings, which `scripts/moduleconstants.py` already does for a module without importing it,
would reach the logger and no further in two of them: `test_abandon.py` interpolates a message it
imports from the module under test, and `test_converse.py:530` one that `pytest.mark.parametrize`
hands in, which no reading of the source binds to one string.

## Trail

- 2026-09-05: opened by the close of
  [R-523](523-the-tool-audit-line-is-described-in-prose-because-its-fields-vary-by-condition.md),
  whose reader's suite pins the f-string as left unread and says nothing about reading it.
- 2026-09-12: verified against the code, with the trigger narrowed and two claims in the body
  repaired. The trigger has not fired: every `assert` in `brain/packages/tools/tests/test_audit.py`
  whose test is one `==` and which renders a line opening with a level has a string constant on one
  side, and `assertedlines.proven` returns all six of them. Two of the entry's readings of the
  reader were wrong. Only the expected side has to be a constant, since `_equated` reads both sides
  and takes whichever one `_rendered` accepts, and the suite's last whole-line assertion already
  binds the rendered side to `line`; the trigger clause that made a bound name fire is corrected to
  say which side it is about. And the fault does point at the suite: it names the suite directory
  and lists the field lists asserted whole there, which is `none` for a sink whose assertions all
  moved into an f-string, so what misleads is the runbook anchor rather than the words.

  One property was checked because a sibling sweep found the constant registry matching a rendered
  needle against a whole file rather than one line. This reader has the opposite shape and nothing
  in the entry rests on the wrong one: `SAMPLE.match` is anchored at the start of one string
  constant, a constant carrying a newline is refused by `_rendered`, and the doc side reads one
  markdown line at a time with its own backslash continuations folded in first.

  What a close would cost is unchanged, and so is the reason it is not paid: no suite writes either
  shape, so the f-string case would still be written against no example.
- 2026-09-14: verified again, with nothing in the body repaired. The trigger has not fired. Every
  `assert` in `brain/packages/tools/tests/test_audit.py` whose test is one `==` was listed and read,
  fifteen of them: ten carry a one-line string constant on a side and five do not, and none of
  those five would render a line opening with a level. Two compare a tuple of fields against a
  tuple of values, one compares the result size against an integer, one counts how often the
  message appears in a line carrying a forgery, and one compares a single rendered value against a
  concatenation. `assertedlines.proven` returns the same six lines for the sink.

  One thing about the reach of this reader was derived while checking, and it raises what a close
  is worth. `samplecheck.disagreement` sends every call whose field list the source refuses to
  `_proven`, not only the audit sink's, so the reader is consulted for the four call-shaped
  refusals [R-619](619-four-refusal-lines-attach-their-fields-by-a-call.md) is about as well. No
  runbook prints one of those four today, so nothing turns on it yet. What changes is the cost of
  leaving this open: a suite asserting one of those lines through an f-string would leave that
  sample unheld the same way, so the shapes this reader refuses now stand between four more lines
  and being documentable rather than one sink's.
- 2026-09-15: verified again, with the trigger narrowed, the reason for leaving it weakened and
  its reach widened. The trigger as written fired on the shape existing anywhere, and the shape now
  exists:
  `brain/packages/core/tests/test_log_format.py:336` asserts a whole line through an f-string,
  `f"INFO:cortex.test:hello api_key={REDACTED}"`, and `brain/packages/core/tests` is a suite this
  reader is consulted over, being the suite beside `cortex_core/residency_watch.py` whose refusal
  line it would hold. Nothing is unheld by it: the logger is `cortex.test`, which no module under
  the brain declares, so a sample of that line fails at the logger before the suite is read. So the
  entry's reason for leaving the case unbuilt is now half dead, a fixture having something to be
  written against, and the other half stands, no line wanting it. The trigger above is narrowed to
  the line whose logger a brain module declares, which is the assertion that would leave a runbook
  sample unheld. `brain/packages/tools/tests`
  still writes ten `==` asserts carrying a one-line string constant and five that do not, none of
  the five rendering a line opening with a level, and `assertedlines.proven` returns the same six
  lines for the sink. What did move is reach: `docs/runbooks/model-swap.md` now prints the refusal
  line of `cortex_orchestrator/swap_builders.py`, held to a whole line `test_swap_wiring.py`
  asserts, so this reader is load-bearing for two package suites rather than one, where the
  2026-09-14 bullet recorded that no runbook printed a call-shaped refusal at all. The
  orchestrator's suite writes 553 single-`==` asserts and none of them is an unread whole line.
  Recorded in the ADR-0009 addendum holding three sample-gate triggers to the tree.
- 2026-09-19: re-derived, and the trigger as narrowed on 2026-09-15 had already fired the day it was
  written. `brain/packages/orchestrator/tests` is a suite this reader is consulted over, being the
  one beside `cortex_orchestrator/swap_builders.py` and `cortex_orchestrator/bounds.py`, and it
  asserts three whole lines through f-strings, `test_abandon.py:485` for
  `cortex_orchestrator.abandon` and `test_converse.py:530` and `:592` for
  `cortex_orchestrator.converse_stream`, all dating from 2026-08-19 and 2026-08-20. Both loggers are
  declared by brain modules, so the clause held; the last bullet's reading that none of the
  orchestrator's single-`==` asserts is an unread whole line was wrong. Nothing is unheld by them,
  because those calls' field lists are read off the calls and `_proven` is reached only for a
  refused one. So the trigger is narrowed again, to a line of a refused call, and the refused calls
  are counted: the tool audit, the swap refusal, the two bounds refusals and the residency watch's
  worst-stop line. Of those only the first two are asserted whole in any shape; the bounds lines
  are checked by containment and the residency line by its message and its field mapping. The
  core suite gained a second `cortex.test` f-string on 2026-09-17, at `test_log_format.py:334`,
  and the one the body cited has moved to line 415. The body's account of the close is repaired
  as well, since the shape the tree writes interpolates the logger, which the planned reading could
  not match. The counts the last bullet gave for the tools suite were for `test_audit.py` alone,
  which still writes fifteen single-`==` asserts, ten with a one-line string constant; the
  orchestrator's suite now writes 558.
