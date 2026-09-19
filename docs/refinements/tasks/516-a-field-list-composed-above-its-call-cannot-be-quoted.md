# A field list composed above its call cannot be quoted

**Status:** done 2026-09-02
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`logcalls._keys` reads a field list off `extra=` when that keyword's value is a dict written out at
the call, and raises on every other form. Three of the brain's log calls are written another way:
`cortex_core/brain_phase.py` builds one `extra` above the two lines that report the decode reading
and hands it over, the warning as `extra | {"shortfall": reading.shortfall}` and the reading as the
bare name, and `cortex_tools/audit.py` composes its `fields` across statements and by condition. A
fenced sample of any of the three fails `check-samplecheck` with `extra= is not a mapping written
out at the call`, which is a check failing on a document nothing is wrong with.

What it costs: the spill warning is the one line the swap runbook exists to explain, its own comment
sends a reader to that runbook, and it is prose there because it cannot be a sample. Prose is
compared with nothing, and it had gone stale, with six field names in an order the formatter does
not print and three fields missing. Writing both dicts out at their calls was declined, since it
would put the same eight keys in `brain_phase.py` twice for a reader's benefit and let one move
without the other (ADR-0045 decision 10).

## History

- 2026-08-30: opened by the close of
  [R-505](505-the-spill-line-a-runbook-describes-and-never-prints.md), which measured three of five
  lines refused for their fields after all five had been made findable by their message.
- 2026-09-02: closed as the tractable middle with four conditions on it (ADR-0045 decision 9). Every
  claim held; only the line numbers had moved, the three refusals now at 210, 212 and 89.
  `scripts/logfields.py`, split off `logcalls.py` at the line cap, follows a bare name and a name
  unioned with a literal to one binding at the top of the enclosing function's body above the call,
  and only when nothing else in the function names it, so the tool audit's line is refused at its
  first `update` rather than guessed, as this entry argued. The swap runbook now prints all three
  lines of the spill watch as fenced samples and restates none of them in prose, which also closed
  [R-519](519-a-runbook-restates-a-declared-message-as-a-wrapped-prefix-nothing-ties.md). Opened
  [R-522](522-a-union-spelled-as-a-spread-of-the-bound-name-is-still-refused.md) for the `**` spread
  form of the union, which stays refused, and
  [R-523](523-the-tool-audit-line-is-described-in-prose-because-its-fields-vary-by-condition.md) for
  the tool audit's field prose.
