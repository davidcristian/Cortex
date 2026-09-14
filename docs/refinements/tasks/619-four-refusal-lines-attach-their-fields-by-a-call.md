# Four refusal lines attach their fields by a call no reader follows

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** the first runbook that wants to print one of these four lines as a fenced sample,
which is the same event that fired for the spill warning; `check-samplecheck` then fails on that
document with the proven path's fault, which quotes the refusal, names the `tests` directory beside
the module and reports that nothing there is asserted whole with those fields.
**Verified:** 2026-09-14

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
anything, and the `ERROR` line beside it would be refused as a sample even though it is now a
constant message the reader can find.

**What would close it.** Either of two shapes, and the choice is the work. A reader that follows a
call to a function in the same module and reads the mapping it returns would cover all four and
would be a wider reader than the composed-fields addendum was willing to be, so it needs that
addendum's argument answered rather than repeated. Asserting each line whole in its own package's
suite is the other shape, and it needs no new reader and no registration anywhere:
`samplecheck.disagreement` sends every call whose field list the source refuses to `_proven`, which
reads the `tests` directory beside the module's `src`, so one whole-line assertion in
`brain/packages/orchestrator/tests` or `brain/packages/core/tests` is all a sample of one of these
four would need. Its cost is a second place each line is written down.

## Trail

- 2026-09-10: opened by the close of
  [R-331](331-five-raised-messages-keep-their-numbers-in-prose.md), which split six logged-and-raised
  messages into a constant log message and a self-contained exception and, in doing so, added the
  third and fourth call-shaped `extra=` in the brain.
- 2026-09-14: verified against the code, with the trigger and one of the two closes repaired. The
  count holds: walking every brain module and reading each log call's `extra=` refuses exactly five
  of the 102 calls, the four named above and the tool audit's, whose mapping is bound and grown by
  condition rather than handed over by a call. The trigger has not fired, no runbook quoting any of
  the four.

  Two claims in the entry were wrong about the gate, and both make the second close cheaper than it
  was written. Nothing names the tool audit's line in `assertedlines.py`; `disagreement` catches the
  refusal for any call at all and hands it to `_proven`, which reads the suite beside that module's
  `src`. So the four lines already reach that path, and what stands between them and a runbook is a
  whole-line assertion in the orchestrator's or the core's own suite, not a change to any reader.
  And the fault a writer would meet is not the bare refusal. Appending a sample of the swap
  refusal to `docs/runbooks/model-swap.md` and running the gate printed one miss, `prints
  deadline_s, probe_timeout_s, reap_timeout_s, stop_grace_s, worst_s where
  brain/packages/orchestrator/src/cortex_orchestrator/swap_builders.py:209: extra= is not a mapping
  written out at the call, nor a name the enclosing function binds to one, and no line under
  brain/packages/orchestrator/tests is asserted whole with those fields (asserted whole there:
  none)`, and the sample was removed again. That fault names the file the assertion goes in, so it
  points at the work rather than at a document nothing is wrong with, and the trigger above is
  corrected to say so.

  This entry and
  [R-554](554-a-whole-line-asserted-through-an-f-string-or-a-helper-is-not-read-as-proven.md) were
  read together on the guess that they are one defect seen twice, and they are two. This one is
  about `logfields.py` refusing a call-shaped `extra=`; that one is about which expected sides
  `assertedlines.py` reads out of an equality. They meet only at the proven path, which is this
  entry's cheaper close and that entry's subject, so widening the reader there raises what the
  assertion route can be written as.

  What the tree said about this was corrected in the same session. `scripts/samplecheck.py`,
  `scripts/assertedlines.py` and `docs/modules/repo-gates.md` all described the refused set as one
  call, the tool audit's, which was true until these four lines were written and is what this entry
  was filed against. They now name both shapes and say that every refused call reaches the suite
  beside its own module.
