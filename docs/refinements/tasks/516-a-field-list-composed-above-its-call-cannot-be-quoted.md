# A field list composed above its call cannot be quoted

**Status:** landed 2026-09-02
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-30 by the close of
[R-505](505-the-spill-line-a-runbook-describes-and-never-prints.md), which set out to print the
lines the reader had just become able to find and could print only one of them.

`logcalls._keys` reads a field list off `extra=` when that keyword's value is a dict written out at
the call, and raises on every other form. Three of the brain's log calls are written another way:
`cortex_core/brain_phase.py` builds one `extra` above the two lines that carry the decode reading
and hands it over, the warning as `extra | {"shortfall": reading.shortfall}` and the reading as the
bare name, and `cortex_tools/audit.py` composes its `fields` across statements and by condition. A
fenced sample of any of the three fails `check-samplecheck` with `extra= is not a mapping written
out at the call`, which is a gate failing on a document nothing is wrong with, the same shape as the
message fault that was fixed this morning and a different cause.

**What it costs today.** The spill warning is the one line the swap runbook exists to explain, its
own comment sends a reader to that runbook, and it is prose there because it cannot be a sample.
Prose is held by nothing, and it had drifted: six field names in an order the formatter does not
print, with three fields missing. That was corrected by hand and can drift again by hand, which is
the whole argument for a sample.

**What to weigh.** The reading is a dataflow question rather than a syntax one, so it is wider than
the name resolution beside it. A tractable middle is the two shapes actually in the tree: a bare
name bound to a dict literal in the same function, and that name unioned with a dict literal at the
call. Both are read without executing anything and both stop at the function they are written in.
Weigh against that what happens when the reader is nearly right: a field list read from a branch
that does not run would hold a document to a line nothing prints, which is worse than raising.
`audit.py` is the case that argues for refusing rather than guessing, its `fields` gaining keys
under conditions, and it may stay unquotable on purpose.

**What was declined, so it is not re-proposed.** Writing both dicts out at their calls, which would
put the same eight keys in `brain_phase.py` twice for a reader's benefit and let one move without
the other. The code does not bend to the gate's reader (ADR-0009 quotable-line addendum).

## Trail

- 2026-08-30: opened by the close of
  [R-505](505-the-spill-line-a-runbook-describes-and-never-prints.md), whose re-derivation measured
  three of five lines refused for their fields after all five had been made findable by their
  message.
- 2026-09-02: **landed** as the tractable middle with four conditions on it (ADR-0009
  composed-fields addendum). Re-derivation held every claim; only the line numbers had moved,
  the three refusals standing at 210, 212 and 89. `scripts/logfields.py`, split off
  `logcalls.py` at the line cap, follows a bare name and a name unioned with a literal to one
  binding at the top of the enclosing function's body above the call, and only when nothing
  else in the function names it, so the tool audit's line is refused at its first `update`
  rather than guessed, as this entry argued. The swap runbook now prints all three lines of the
  spill watch as fenced samples and restates none of them in prose, which closed
  [R-519](519-a-runbook-restates-a-declared-message-as-a-wrapped-prefix-nothing-ties.md) as
  well. Opened
  [R-522](522-a-union-spelled-as-a-spread-of-the-bound-name-is-still-refused.md) for the `**`
  spread spelling of the union, which stays refused, and
  [R-523](523-the-tool-audit-line-is-described-in-prose-because-its-fields-vary-by-condition.md)
  for the tool audit's field prose, held by nothing.
