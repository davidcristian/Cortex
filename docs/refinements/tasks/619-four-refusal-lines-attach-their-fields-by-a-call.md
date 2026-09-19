# Four refusal lines attach their fields by a call no reader follows

**Status:** done 2026-09-14
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`logfields.py` reads a log call's `extra=` in three forms: a mapping written out at the call, a bare
name bound to such a mapping at the top of the enclosing function, and that name unioned with a
mapping written out. Anything else is refused rather than guessed at
([ADR-0045](../../adr/ADR-0045-documented-log-lines.md) decision 9), because a field list read off
something a branch may have changed would compare a document against a line nothing prints.

Four of the brain's log calls pass a call's return value instead, all about the two bound pairings.
`cortex_orchestrator/bounds.py` passes `_pairing(subagents, tools)` on both the passing line and
the refusal, and `cortex_orchestrator/swap_builders.py` and `cortex_core/residency_watch.py` each
pass `bounds.pairing_fields(deadline_s)` on their refusal. The last two were written that way on
purpose: both describe the same comparison and must attach the same set, and building the set once
is what guarantees that.

This cost nothing while no runbook quoted any of the four. What it prevented was quoting one: the
swap runbook printed the control deadline's exception text with nothing checking it, and the
`ERROR` line beside it would have been refused as a sample.

**What closed it.** `docs/runbooks/model-swap.md` now prints the control deadline's refusal as a
fenced sample beside the exception text, checked against a whole-line equality in
`brain/packages/orchestrator/tests/test_swap_wiring.py`, where two containment checks over the same
rendered line stood before. That route needed no new reader: `samplecheck.disagreement` sends every
call whose field list the source refuses to `_proven`, which reads the `tests` directory beside the
module's `src`. The check now reports 15 samples in 12 runbooks with 6 checked against a suite's
assertion, one more of each than the day before.

Widening the reader was declined. Following a call to a function in the same module covers two of
the four, since `swap_builders.py` and `residency_watch.py` call `pairing_fields` on a local whose
class the source never states, a frozen dataclass in a third module of another package. A reader
that reached those would infer a type across packages from a name, and the narrower one would read
a `return` statement as though a function had one and it were unconditional, which is exactly what
decision 9 declined. The rule and the two-step route a later runbook follows are
[ADR-0045](../../adr/ADR-0045-documented-log-lines.md) decision 11. The other three call-shaped
lines have no sample and need none.

## History

- 2026-09-10: opened by the close of
  [R-331](331-five-raised-messages-keep-their-numbers-in-prose.md), which split six
  logged-and-raised messages into a constant log message and a self-contained exception and, in
  doing so, added the third and fourth call-shaped `extra=` in the brain.
- 2026-09-14: checked against the code, with the trigger and one of the two closes repaired. The
  count holds: reading each log call's `extra=` across every brain module refuses exactly five of
  the 102 calls, the four named above and the tool audit's, whose mapping is bound and grown by
  condition. Two claims were wrong about the check, and both make the assertion route cheaper than
  written: nothing names the tool audit's line in `assertedlines.py`, and the fault a writer meets
  is not a bare refusal but a message naming the file the assertion goes in, which was confirmed by
  appending a sample of the swap refusal to `docs/runbooks/model-swap.md`, running the check and
  removing the sample again. This entry and
  [R-554](554-a-whole-line-asserted-through-an-f-string-or-a-helper-is-not-read-as-proven.md) were
  read together on the guess that they are one defect seen twice, and they are two: this one is
  about `logfields.py` refusing a call-shaped `extra=`, that one about which expected sides
  `assertedlines.py` reads out of an equality. `scripts/samplecheck.py`, `scripts/assertedlines.py`
  and `docs/modules/repo-checks.md` all described the refused set as one call and were corrected in
  the same session.
- 2026-09-14: done by the assertion route, with the reader widening declined in the same pass.
