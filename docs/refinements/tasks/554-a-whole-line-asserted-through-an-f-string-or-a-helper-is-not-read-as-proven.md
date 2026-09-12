# A whole line asserted through an f-string or a helper is not read as proven

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-12
**Trigger:** a whole-line assertion in a sink's own suite whose expected line is not a plain string
constant: an f-string interpolating the fixture's timestamp, a name the expected line is bound to
above the assert, or a helper that builds or compares it. Countable by listing a suite's `assert`
statements whose test is one `==` and neither side of which is a one-line string constant, and
reading whether either side would render to a line opening with a level. Binding the *rendered*
side to a name fires nothing, and the audit suite already writes one assertion that way.

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
part shape. A helper cannot be read without executing it, and stays refused. Not built, because
no suite writes either and a case written against no example is a guess about a shape nobody has
asked for.

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
