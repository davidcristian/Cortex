# A whole line asserted through an f-string or a helper is not read as asserted

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)
**Verified:** 2026-09-19
**Trigger:** a whole-line assertion whose expected line is not a plain string constant (an f-string,
a name the expected line is bound to above the assert, or a helper that builds or compares it) and
whose logger and message belong to a call whose field list the code reader cannot read, since only
such a call's samples go through this reader. Count it in two steps: list the calls the reader
cannot read by running `logcalls.logged` over every message `logcalls.messages` returns and keeping
those that raise `UnreadFieldsError`, five calls in four modules on 2026-09-19; then read the
package suite beside each for an `assert` whose test is one `==`, with neither side a one-line
string constant, that would produce one of those calls' logger and message. Binding the produced
side to a name does not count, and the audit suite already writes one assertion that way.

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
values are dropped anyway. That is one more case in `_rendered` plus a fixture per part form, and a
refusal for an f-string whose expression stands where a field name would, which no reading of the
source can supply. A helper cannot be read without running it and stays refused. It is not built
because no line anybody could document is asserted either way, and because every f-string whole line
in the tree interpolates its logger from a constant the test module binds, which the planned reading
could not match.

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
