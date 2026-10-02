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

**Where it came from, read from the code.** Before the fix, `BrainPhase.run` sent the deep model
the stored history and then `record.loop_tail`. The tail ended with the `escalate_to_brain` result,
`ESCALATION_QUEUED_MSG`, which tells the model reading it to wrap up by telling the user in a
sentence or two what is being handed off: an instruction to the cortex, read by the deep model as
the last message in its context. A second cause sat in the history: the cortex's own reply to this
turn ("I am handing this task over to the deep reasoning model to provide..."), stored before the
handoff starts, came before the tail, so the deep model read a finished handoff reply as the turn's
answer so far. A third may be the client's prompt, which told the model not to answer the question
itself; the deep model reads the user's text too.

**What was built.** The deep model's context now ends with a message addressed to it
(`cortex_core/handoff_view.py`, ADR-0030 decision 4 step 4): the escalation's result is replaced
by `HANDOFF_TAKEN_MSG` with the brief, which says the handoff is done, the task is the deep
model's, and the user has already been told, and the cortex's reply to this turn is left out of
the history it reads. The store is unchanged. It is a tool result, not a system message, because
the Qwen3.5 template refuses a system message that is not first (ADR-0071). The contract test is
`test_the_deep_models_context_ends_with_the_handoff_addressed_to_it` over the scripted host, with
the real tool's result in the tail. The client's default prompt now leaves the answer to the deep
model instead of forbidding one (`body/crates/rpc/tests/handoff_live.rs`), so later rows do not ask
the deep model to refuse.

**The verifying row, written before its draw.** `777swap`
(`measurements/sitting-2026-10-02b/drivers/777swap.sh`, appended after `772killb`) first tags
`cortex-brain:r777`, built from the fix's commit under its own tag so no 772 row could draw it, as
`cortex-brain:latest`, then runs three approved handoffs on one stack at the shipped caps. h1 and
h2 send the old prompt, which forbids an answer; h3 sends the new one. The replies are in
`measurements/sitting-2026-10-02b/777swap.h1.txt` to `h3.txt`, the brain log in `777swap.logs.txt`.
A reply answers when it explains the sum (it names odd numbers and a square, n^2 or n squared) and
is more than a sentence about the handoff.

- Prediction: h1, h2 and h3 all answer. The context cause alone explains 7 of 7, so the old prompt
  does not stop the deep model once its last message says the task is its own.
- If h1 and h2 restate the handoff and h3 answers, the prompt is a cause as well, and the prompt
  change already made covers it; record that in the readings.
- If h3 restates the handoff too, the context change did not reach the cause: read the deep model's
  request in the row's brain log before building anything else.
- A row that fails to complete a handoff decides nothing; it is run again, not read.

## History

- 2026-10-02: filed from R-772's card rows, where every completed handoff produced this reply.
- 2026-10-02: the cause found in the code (the tail's last message and the cortex's reply both
  addressed the turn's wrap-up), the deep model's context changed to end with a message to it,
  and the client's prompt changed; `777swap` queued with its prediction above.
