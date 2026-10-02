# The deep model restates the handoff instead of answering

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-10-02

In every handoff R-772's card rows completed on 2026-10-02, 7 of 7 on the 24 GB card with the
shipped deep pick, the deep model's whole reply was one sentence saying the task had been handed to
the deep model ("I have handed this task over to the deep model, which will provide a two-sentence
explanation of why the sum of the first n odd numbers equals n^2."), 35 to 97 tokens, and never the
answer. The client output is `measurements/sitting-2026-10-02b/772swap.h*.txt` and
`772caps.m*.txt`; the readings are in
[model swap](../../readings/model-swap.md#a-handoff-through-the-conductor).

**Where it comes from, read from the code and not yet tested.** `BrainPhase.run`
(`cortex_core/brain_phase.py`) sends the deep model the assembled history and then
`record.loop_tail`, the cortex's own working messages after the history (`EscalationSlot.snapshot`
in `cortex_core/handoff.py`). That tail ends with the `escalate_to_brain` result,
`ESCALATION_QUEUED_MSG` in `cortex_core/escalate.py`, which tells the model reading it to wrap up
by telling the user in a sentence or two what is being handed off. That text is addressed to the
cortex, and the deep model reads it as the last instruction in its context. The card rows' prompt
also told the model not to answer the question itself, which the deep model reads too
(`_user_query` recovers the user's text from the store).

**What to build.** First a row that separates the two causes: the same handoff with a prompt that
does not forbid an answer, and a deep phase whose context ends with a message addressed to the
deep model (the brief, and that the handoff has happened). Write its rule and prediction here
before the draw. The fix changes shipped behaviour, so it is made only if the row shows the tail is
the cause; it then goes behind a contract test over the scripted host that asserts the deep
model's context does not end with a message addressed to the cortex.

## History

- 2026-10-02: filed from R-772's card rows, where every completed handoff produced this reply.
