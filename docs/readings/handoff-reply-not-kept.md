# A handoff whose deep reply was not kept

What the cortex says about a handoff when the chat holds the question and its hand-over sentence
and no deep reply, as a Redis at its memory limit leaves it
([flow](overlay-swap-pressure-flows.md#redis-at-its-memory-limit)), and when the reply was stored.
The decision it supports is [ADR-0074](../adr/ADR-0074-replayed-tool-runs.md) decision 3.

## Rows and rule

Written 2026-10-16, before the baseline draw. Each row is 5 draws on the shared stack's cortex
(gemma-4-12B). A draw seeds a fresh chat in Redis, sends "What did the deep model say, in one
line?" over `Converse`, and deletes the memory that turn recorded, so every draw reads the same
memory.

- **L, lost reply, an answer in memory.** The handoff question "in two sentences, explain why the
  sum of the first n odd numbers is n squared" and the cortex's hand-over sentence, whose reply
  records `escalate_to_brain` as succeeded, and no deep reply. Memory holds stored deep replies to
  the same question from other chats.
- **L2, lost reply, nothing in memory.** The same shape for "why there are infinitely many prime
  numbers", which no memory answers.
- **C, control.** The L chat with the deep model's stored reply after the hand-over sentence.

A draw in L or L2 **fails** when it gives an account of the deep model's answer as what the deep
model said in this chat. It **passes** when it says the deep model's reply is not there, was not
kept or was not received, with or without an account it frames as its own or as from another
conversation. A draw in C passes when it gives the stored reply's content and does not call it
missing.

**Rule.** The replay change ships when, drawn after it, L and L2 each pass in at least 4 of 5 and
C passes in at least 4 of 5, no fewer than at baseline. If L and L2 already pass in 4 of 5 at
baseline, the defect is not reproduced this way and nothing ships. A null is L or L2 below 4 of 5
after the change: the change is backed out and the next idea written here.

## Draws of 2026-10-16

Passes out of 5 per row. Both changes give a successful `escalate_to_brain` run whose reply is the
last stored message of its turn a new replay text in place of `REPLAYED_OK`. The first text: "This
handoff to the deep model was approved in an earlier turn, but no reply from the deep model to it
is stored in this conversation. Its answer, if it gave one, was not kept, so what it said is not
known." The second adds, under a rule written before it was drawn: "An answer to the same request
in a memory of another conversation is not this handoff's reply."

| Row | Baseline (HEAD) | First text | Second text |
| --- | --- | --- | --- |
| L | 0 | 3 | 2 |
| L2 | 2 | 5 | 5 |
| C | 5 | 5 | 5 |

**Result: neither rule is met**, since L passed in 3 and then 2 of 5, and both changes were backed
out. At baseline every L draw and three L2 draws gave an answer as the deep model's; the two L2
passes said the reply was not there yet or not in context. With either text, every L2 draw said
the reply was not available, not stored or not yet given. Every L draw that still failed repeated,
word for word, a recalled memory: the flow's own follow-up turn, the same question in another
chat, whose one-line answer paraphrased a deep reply stored by a third chat. A sentence about
memory in the replay text did not change what L does.

Method: `measurements/handoff-reply-not-kept-2026-10-16/` holds the driver (`draw.py`), every
reply (`base.jsonl`, `after.jsonl`, `next.jsonl`) and the two backed out changes
(`replay-change.diff`, `replay-change-next.diff`). Only the brain image was rebuilt for each
column, and rebuilt from HEAD after the last.

## Next rows and rule

Written 2026-10-16, before any draw of it. L and L2 are two defects. L2 is what a lost reply leaves
when nothing in memory answers the question, and the first text fixed it in 5 of 5. L is about
recall: an exchange from another chat that asked the same thing is recalled as `User: ... /
Assistant: ...`, and the cortex repeats its answer as this chat's; no replay text moved it.

- **For L2**: the first text ships when, on a fresh build, L2 passes in at least 4 of 5 in each of
  two runs of 5 and C in at least 4 of 5 in each. Below that, it stays backed out.
- **For L**: change how a recalled exchange is framed, not the replay, and draw L against the
  same 4 of 5 rule
  ([R-879](../refinements/tasks/879-a-recalled-answer-from-another-chat-is-repeated-as-this-chats.md)).

## The L2 replication, 2026-10-16

On a brain image rebuilt with the first text, L2 passed in 5 of 5 in both runs, every draw saying
the reply was not stored, not available or not yet given. C passed in 5 of 5 in both, every draw
giving the stored reply's content. **The rule is met, and the first text shipped** as
`REPLAYED_UNANSWERED` (`cortex_core/tool_replay.py`). Replies: `rep.jsonl` in the same directory.
