# A time before the verb of a second clause loses the reminder tool

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-11-09

`_ACTION` in `memory_request.py` reads a clause that opens with a verb, and `at` is in its list of
words no clause may open with. `Remember my code is 5521 and at 9 ring me.` then has no action
clause, so `unasked_tools` refuses `schedule_task` and `set_volume` on a message that asks for a
ring at 9 ([readings](../../readings/side-effect-tools-second-clause.md#audit-replay-of-the-time-clause-2026-11-09)).
A tool refusal's safe direction is to keep the tool.

## What to do

1. Write near misses first: `Remember I arrive at 9 on Mondays.` and `Remember the shop opens at
   9.` must still refuse both tools.
2. Read a time (`at`, `around`, `by` or `before` and a digit) before the clause's verb, and replay
   every recorded draw message in `docs/readings/` through the old and new reader.

## History

- 2026-11-09: filed from the audit replay of the time clause.
