# Four refusal lines attach their fields by a call no reader follows

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** the first runbook that wants to print one of these four lines as a fenced sample,
which is the same event that fired for the spill warning; `check-samplecheck` then fails with
`extra= is not a mapping written out at the call` on a document nothing is wrong with.
**Verified:** 2026-09-10

Opened 2026-09-10 by the close of
[R-331](331-five-raised-messages-keep-their-numbers-in-prose.md), which made two more log calls
hand their fields over as a call's return value.

`logfields.py` reads a call's `extra=` in three spellings: a mapping written out at the call, a
bare name bound to such a mapping at the top of the enclosing function, and that name unioned with
a mapping written out. A call is none of the three and is refused rather than guessed at, which is
the composed-fields addendum's rule and is right: a field list read off something a branch may have
changed would hold a document to a line nothing prints.

Four of the brain's log calls are now written that way, all of them about one of the two bound
pairings. `cortex_orchestrator/bounds.py` passes `_pairing(subagents, tools)` on both the passing
line and the refusal. `cortex_orchestrator/swap_builders.py` and `cortex_core/residency_watch.py`
each pass `bounds.pairing_fields(deadline_s)` on their refusal. The two new ones were written that
way deliberately: both describe the same comparison and have to attach the same set, and building
the set once is what guarantees that, where two mappings written out would only happen to agree.

**What it costs today, which is nothing.** No runbook quotes any of the four, so `samplecheck.py`
is never asked about them and the gate is green. What is unavailable is the ability to quote one:
the swap runbook prints the control deadline's *exception* text in a fence today, unheld by
anything, and the `ERROR` line beside it could not be printed as a sample even though it is now a
constant message the reader can find.

**What would close it.** Either of two shapes, and the choice is the work. A reader that follows a
call to a function in the same module and reads the mapping it returns would cover all four and
would be a wider reader than the composed-fields addendum was willing to be, so it needs that
addendum's argument answered rather than repeated. Naming these lines in `assertedlines.py`
instead, the way the tool audit's is, holds them to a whole line their own suite asserts and needs
no new reader, at the cost of a second place each line is written down.

## Trail

- 2026-09-10: opened by the close of
  [R-331](331-five-raised-messages-keep-their-numbers-in-prose.md), which split six logged-and-raised
  messages into a constant log message and a self-contained exception and, in doing so, added the
  third and fourth call-shaped `extra=` in the brain.
