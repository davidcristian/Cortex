# A whole line asserted through an f-string or a helper is not read as proven

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** a whole-line assertion in a sink's own suite whose expected line is not a plain string
constant: an f-string interpolating the fixture's timestamp, a name bound to the line above the
assert, or a helper that builds or compares it. Countable by listing a suite's `assert` statements
whose test is one `==` and whose neither side is a string constant, and reading whether either side
would render to a line opening with a level.

Opened 2026-09-05 by the close of
[R-523](523-the-tool-audit-line-is-described-in-prose-because-its-fields-vary-by-condition.md),
which taught `scripts/assertedlines.py` to read the rendered lines a suite asserts whole.

The reader reads a string only where it is one side of `assert x == "..."`, as a constant the
parser has already joined from its adjacent literals. That is every whole-line assertion the tool
audit's suite writes today, and it is the shape the reader was built against. A suite that moved
its expected line into an f-string, say to interpolate `_AT.isoformat()` rather than spell the date
twice, or into a helper taking the fields and rendering the line, would leave every runbook sample
of that sink unheld. The gate fails closed rather than open, which is the right direction, but the
fault it prints is about the runbook, `no line under brain/packages/tools/tests is asserted whole
with those fields`, for a change made in the suite, and an author reading it would look in the
wrong file first.

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
