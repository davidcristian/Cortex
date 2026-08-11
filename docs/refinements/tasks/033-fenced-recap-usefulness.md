# The fenced recap's measured usefulness

**Status:** landed 2026-08-06
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

**A fenced recap's usefulness was measured 2026-08-06 and the fence is not what costs
([ADR-0038 re-measured-behind-the-fence addendum](../../adr/ADR-0038-ranked-recall.md)); the
default stays off all the same, on the user's decision, against numbers the same run
falsified.** The question was whether a cortex told the recap is quoted data would still quote a
booking reference out of it. It does: three runs of the recorded live test, and behind the fence
the reply is "Your booking reference is QH7-4412." exactly as it read unfenced, with the shipped
window failing to answer all three times. **The control is now asserted rather than printed**,
which is the trap this repo has fallen into twice: an arm that answers anyway has measured
nothing, so the test fails instead of reporting a comparison with no contrast in it. So is the
absence of fence markers from the reply, a defect that would have been visible only by reading
the output. **What the fence costs is characters, not the answer:** the same 484-character
account reaches the model as a 1022-character message once its standing preface and two markers
are around it, so the recap message roughly doubled while the account inside it did not change.
The fold also got slower, 11.0 s unfenced against 15.2 s and 23.6 s here, which is partly the
larger prompt and partly run variance, and is dwarfed by what follows. **What stopped the default
is the case a default runs in**, and it is written up as its own finding on the two entries above:
five folds compound, retention was 2 of 3, and a fold reached 224.5 s. The user had decided to
turn the summary on and accepted 11 s per boundary move; that premise is what this run
falsified, so the knob stays one env variable away rather than shipping against its own numbers.
The live test now carries both arms, the single fold and the staged one
(`packages/inference/tests/test_history_recap_live.py`, integration-marked), and reports
retention as a rate rather than asserting it, since asserting a probabilistic model behaviour
pins the model rather than the code. Remaining from this deferral: nothing of its own, the four
things a default move waits on being the two entries above, the disable-thinking lever in
[inference-model-manager.md](../index.md#inference-model-manager), and the fold's silence, opened above.

## Trail

- 2026-08-06: Opened when the recap of tainted turns was fenced, since the live run that measured
  the recap's usefulness had been made before the fence existed.
- 2026-08-06: Measured the same day. Behind the fence the cortex still answers "Your booking
  reference is QH7-4412." out of a recap it has been told is quoted data, three runs of three,
  with the shipped window failing all three and no fence marker reaching the reply. Both the
  control and the marker absence are assertions now rather than printed output.
