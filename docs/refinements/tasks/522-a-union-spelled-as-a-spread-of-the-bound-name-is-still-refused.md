# A union spelled as a spread of the bound name is still refused

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** a brain log call spelling its union as `{**extra, "shortfall": ...}` over a name
bound above it, rather than as `extra | {...}`, which is the spelling the deep phase writes today.

Opened 2026-09-02 by the close of
[R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md), which taught
`scripts/logfields.py` to follow a bare name, and a name unioned with a mapping written out at the
call as `extra | {"shortfall": reading.shortfall}`, to one binding above the call.

The other spelling of the same union, a mapping written out at the call that spreads the bound name
into itself, prints the same line and is refused: `_literal` reports a spread as a field name that
is not a plain string, which is what it reported before this reader existed and is right for a
spread of any name the reader would not follow. Reading it would mean treating a `**name` entry
whose name meets the four conditions as the bound mapping's keys and refusing every other spread,
which is one more case in `_named` and a fixture per branch. Not built, because the brain writes
the `|` spelling and nothing else, and a reader case written against no example is a guess about
a shape nobody has asked for. When one arrives, the fault names its line.

## Trail

- 2026-09-02: opened by the close of
  [R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md), whose mutation table
  measures the `|` union read and says nothing about a spread.
