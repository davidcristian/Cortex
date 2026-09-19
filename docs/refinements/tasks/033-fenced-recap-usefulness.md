# The fenced recap's measured usefulness

**Status:** done 2026-08-06
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The question was whether a cortex told the recap is quoted data would still quote a booking
reference out of it. It does: over three runs of the recorded live test, behind the fence the
reply is "Your booking reference is QH7-4412." exactly as it read unfenced, with the shipped
window failing to answer all three times.

The control is asserted rather than printed, which is a mistake this repo has made twice: a
variant that answers anyway has measured nothing, so the test now fails instead of reporting a
comparison with no contrast in it. The absence of fence markers from the reply is asserted too,
being a defect that would otherwise have been visible only by reading the output.

What the fence costs is characters rather than the answer: the same 484-character account reaches
the model as a 1022-character message once its preface and two markers are around it, so the recap
message roughly doubled while the account inside it did not change. The fold also got slower, 11.0
s unfenced against 15.2 s and 23.6 s here, which is partly the larger prompt and partly run
variance.

What kept the default off is the case a default runs in, recorded on
[R-029](029-one-corpus-recap-measurement.md) and
[R-030](030-recap-fold-bounds-and-floor.md): five folds compound, retention was 2 of 3, and a fold
reached 224.5 s. The user had decided to turn the summary on and accepted 11 s per boundary move,
and that premise is what this run falsified, so the setting stayed one environment variable away
rather than shipping against its own numbers. The live test now has both variants, the single fold
and the staged one (`packages/inference/tests/test_history_recap_live.py`, integration-marked),
and reports retention as a rate rather than asserting it, since asserting a probabilistic model
behaviour tests the model rather than the code.

## History

- 2026-08-06: Opened when the recap of tainted turns was fenced, since the live run that measured
  the recap's usefulness had been made before the fence existed.
- 2026-08-06: Measured the same day. Behind the fence the cortex still answers "Your booking
  reference is QH7-4412." out of a recap it has been told is quoted data, three runs of three,
  with the shipped window failing all three and no fence marker reaching the reply. Both the
  control and the marker absence are assertions now rather than printed output.
