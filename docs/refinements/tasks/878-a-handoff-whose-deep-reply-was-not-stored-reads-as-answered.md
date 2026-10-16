# A handoff whose deep reply was not stored reads as answered

**Status:** open, actionable
**Area:** brain-handoff
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)
**Verified:** 2026-10-16

With Redis at its memory limit during a handoff, the deep model's reply is shown but not stored
([readings](../../readings/overlay-swap-pressure-flows.md#redis-at-its-memory-limit)). The chat
then holds the question and the cortex's hand-over sentence, and no deep reply. After the limit
was lifted, "What did the deep model say, in one line?" was answered with a one-line account of
the answer, given as the deep model's words.

What the next turn's cortex reads: the question, the replayed `escalate_to_brain` call with
`REPLAYED_OK` ("This call ran and succeeded in an earlier turn. Its result is not kept."), the
hand-over sentence, and the new question. Nothing in it says that no deep reply followed. Recall
adds earlier exchanges as system context, and in the flow memory held stored deep replies to the
same question from other chats, which the cortex paraphrased. Every handoff that
ends without a stored deep reply leaves this same shape: a refused or failed swap's note is shown
and not stored ([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 6).

## Reproduction

On the shared stack, seed a chat in Redis with the handoff question and the hand-over sentence
(its reply records the run `escalate_to_brain`, ok) and no deep reply, then send "What did the
deep model say, in one line?" over `Converse`. The rows are in the
[readings](../../readings/handoff-reply-not-kept.md).

## What to do

Derive it from the store: a reply whose runs include a successful `escalate_to_brain` and which
is the last message of its turn has no stored deep reply. `replay_runs` gives that call a fixed
text saying so in place of `REPLAYED_OK` (the first text in the readings). It moved row L2, where
nothing in memory answers the question, from 2 to 5 of 5. It was backed out because the rule also
asked for row L, whose failures repeat a recalled answer from another chat and are now
[R-879](879-a-recalled-answer-from-another-chat-is-repeated-as-this-chats.md). Draw the L2
replication in the [readings](../../readings/handoff-reply-not-kept.md#next-rows-and-rule) and
ship the text if it passes.

## History

- 2026-10-16: filed from the Redis memory limit flow on the Linux shell; premise checked against
  the replay and the recall context, and reproduced over `Converse`.
- 2026-10-16: two replay texts for an unanswered handoff drawn against rules written first; both
  fixed L2 and neither fixed L, so both were backed out. L filed as R-879.
