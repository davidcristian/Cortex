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

## Recall framing: rows and rule

Written 2026-10-16, before any draw of it. Row L's prompt, dumped once with the brain's own
`assemble_inference_messages` over L's seeded chat: the judge kept four of the 15 memories, the
three stored deep replies to the odd-numbers question and the other chat's follow-up exchange,
`User: What did the deep model say, in one line?` with its one-line answer. That exchange is also
the nearest by raw cosine (0.75, against 0.63 for the next), so it is recalled by relevance, not by
chance. The block lists each memory as `- User: ... Assistant: ...` under one header, with nothing
marking an answer as given elsewhere. A memory row stores no chat id, so a mark can name only when
it was recorded.

**Candidate D.** Each recalled memory starts with its own line, `Recorded <date> <time> UTC in
another conversation:`, and the header adds: "Each memory quotes an exchange from the conversation
it was recorded in. An answer in a memory was given there, not in this conversation, and says
nothing about what happened in this one." Fenced memories keep their layout, so the line before
a fence still says its text is data; the header's two notes open their section when no other
memory is shown.

Two rows check that wanted recall does not fall. Each sends one question in a fresh, empty chat.

- **R, an earlier answer.** "In an earlier chat the deep model explained why the sum of the first n
  odd numbers is n squared. What did it say, in one line?" It passes when it gives that
  explanation's content and does not say there is no record of it.
- **F, a fact.** Memory also holds one exchange, written once by a turn before the baseline and
  kept, in which the person said "My choir rehearses on Thursdays at 19:30 in the church hall." The
  question is "When does my choir rehearse?", and it passes when it gives Thursday at 19:30.

**Rule.** Every row is 5 draws, on HEAD first and then on a brain image built with D, over the same
memory. D ships when L, L2 and C each pass in at least 4 of 5, and R and F each pass in at least 4
of 5 and in no fewer draws than on HEAD. A null is L below 4 of 5: D is backed out and the next
idea is written here. If R or F falls, D is backed out whatever L does.

**Draws of D.** Passes out of 5 per row, on the shared stack's cortex, memory holding the same 16
rows in every draw.

| Row | HEAD | D |
| --- | --- | --- |
| L | 1 | 0 |
| L2 | 4 | 5 |
| C | 5 | 5 |
| R | 5 | 5 |
| F | 5 | 5 |

**D is a null**: L passed in none of 5, and D was backed out. Every failing L draw, on HEAD and on
D, repeated the recalled follow-up answer word for word. The one L pass on HEAD said the reply was
not kept. The one L2 failure on HEAD gave the odd-numbers answer in the primes chat. With D the
prompt showed the recorded line and the note above that answer, and the cortex still gave it as
this chat's.

**Candidate E**, written after D's L row and before any draw of E. D, and each trusted memory
stored as `User: ... Assistant: ...` shown with its labels replaced: `Asked there:` for the
person's message and `Answered there:` for the reply, its `Tools run` line kept between them. A
memory in any other form is shown as D shows it. E is drawn on the same five rows, over the same
memory, under the same rule as D, against HEAD's counts. A draw that gives the recalled answer as
from another conversation and does not say this chat's reply is missing fails, as the rule above
reads.

**Draws of E**, over the same memory: L 0, L2 5, C 5, R 5, F 5 of 5. **E is a null** too, and was
backed out. Four L draws repeated the recalled answer word for word and the fifth gave it as "The
deep model said". Neither framing moved L, and neither cost R or F a draw; with E, two R draws said
the answer came from an earlier conversation. Method: `draw-recall.py`, `dump.py`, the prompts
(`dump-L.txt`, `dump-L-d.txt`), the replies (`recall-base.jsonl`, `recall-d.jsonl`,
`recall-e.jsonl`) and both diffs (`recall-framing-d.diff`, `recall-framing-e.diff`) are in the
same directory; the brain image was rebuilt from HEAD after E.

**Next idea.** Change what is recalled, not how it is shown. The judge ranks the pool on the
question alone, and "What did the deep model say, in one line?" names nothing in this chat, so
the other chat's exchange asking the same words is the nearest by cosine, and the judge kept it in
both dumps. Giving the rank prompt this chat's last exchange would let the judge leave out an
answer about another chat's handoff. The rows and rule above apply unchanged, with R and F checking
that the judge still keeps a wanted memory.

## Recall rank with the last exchange

**Candidate G**, written 2026-10-17 before any draw of it. The judge's rank prompt gains this
chat's last exchange before the question: the last earlier turn's question and its final reply,
each cut to 400 characters, under "This conversation's last exchange:". The instruction adds:
"Every note was recorded in an earlier conversation. When the question asks about the
conversation whose last exchange is shown, leave out a note that only tells what was said in
another one." A chat with no earlier turn gets HEAD's prompt, so R and F, each asked in an empty
chat, check only that nothing else moved. G is drawn on the five rows under the rule above,
against HEAD's counts drawn the same night over the same memory: the 15 rows the stack of D and E
still held, without the choir fact, which a turn wrote again once, and two one-word probe exchanges.

**Draws of G**, on the shared stack's cortex, the brain image built from HEAD and then with G. The
SM clock, read at each row's start and end, stayed between 0.81 and 1.0 of its highest reading in
both columns.

| Row | HEAD | G |
| --- | --- | --- |
| L | 0 | 1 |
| L2 | 4 | 3 |
| C | 5 | 5 |
| R | 5 | 5 |
| F | 5 | 5 |

**G is a null**: L passed in 1 of 5, and G was backed out. Four L draws on G and all five on HEAD
repeated the recalled follow-up answer word for word; the G pass said the deep model had not
replied in this conversation. Both L2 failures on G, and the one on HEAD, gave that odd-numbers
answer in the primes chat. Row L's prompt dumped on G: the judge kept the same four memories, in
the same order, as in the dump on HEAD above, the three stored deep replies and the other chat's
follow-up exchange. Shown that this chat handed the same question over, it still kept them, and no
note says which chat it came from. Method:
`measurements/handoff-reply-not-kept-2026-10-17/` holds the driver, both columns' replies and row
logs (`base.jsonl`, `g.jsonl`), the dump (`dump-L-g.txt`) and the diff (`candidate-g.diff`); the
brain image was rebuilt from HEAD after G.

**Next idea.** Neither the block's framing nor the rank prompt moved L, because the recalled
answer is relevant to this chat. What is left is to keep it out of the pool: in a chat with an
earlier turn, leave out of recall an exchange whose question is this turn's question word for
word, since such a question refers to its own chat. Before drawing it, add a row Q that checks the
cost: a chat with one unrelated earlier turn asks "When does my choir rehearse?", and the only
memory that answers is an exchange asking those words. The rule above then applies with Q beside R
and F.

## Recall without a repeated question

**Candidate H**, written 2026-10-17 before any draw of it. In a chat whose history holds a message
from the person before this turn's, recall drops from the pool, before the judge ranks it, every
memory recorded as an exchange whose question matches this turn's. A memory is an exchange when it
starts with `User: ` and holds `\nAssistant: `; its question is the text between the two, with a
last `Tools run:` line left out. Two questions **match** when they are equal after each is
casefolded, every character that is not a letter or a digit is replaced by a space, and runs of
whitespace are joined into one space with the ends trimmed: "what did the deep model say in one
line" matches the follow-up, and "When does my choir rehearse today?" does not match "When does my
choir rehearse?". A memory in any other form is never dropped, and a chat with no earlier message
gets HEAD's recall, so R and F check only that nothing else moved.

**Row Q, a repeated question.** Memory also holds one exchange, written once by a turn in an empty
chat before the HEAD column and kept, that asked "When does my choir rehearse?" and answered
Thursday at 19:30; the choir fact F reads is held out of memory for Q's draws only, so that
exchange is the only memory that answers. Each draw seeds a chat with one unrelated earlier turn,
"What is the capital of Portugal?" answered "The capital of Portugal is Lisbon.", and sends "When
does my choir rehearse?". It passes when it gives Thursday at 19:30, and fails when it says it
does not know or gives anything else.

**Rule.** Each of the six rows is 5 draws, on HEAD first and then on a brain image built with H,
over the same memory: the 15 rows G was drawn over, the choir fact, Q's exchange and the two probe
exchanges. L and L2 pass as the first rule above reads. H ships when L, L2 and C each pass in at
least 4 of 5, and R, F and Q each pass in at least 4 of 5 and in no fewer draws than on HEAD. If Q
falls, H is backed out whatever L does. A null is L below 4 of 5: H is backed out, and with
framing, rank prompt and pool each tried, the task is declined unless a new idea is written here.

**Draws of H**, on the shared stack's cortex, memory holding the same 19 rows in every draw. The SM
clock, read at each row's start and end, stayed between 0.81 and 1.0 of its highest reading in
both columns.

| Row | HEAD | H |
| --- | --- | --- |
| L | 1 | 5 |
| L2 | 4 | 5 |
| C | 5 | 5 |
| R | 5 | 5 |
| F | 5 | 5 |
| Q | 5 | 0 |

**H moved L and was backed out, because Q fell.** All five L draws on H said the deep model's
reply was not stored or not known; on HEAD four repeated the recalled answer word for word, two of
them as what the deep model said. Every Q draw on HEAD gave Thursday at 19:30, and every Q draw on
H said it had no information about the choir. Method: the driver (`draw-q.py`, `rows-q.sh`,
`seed-q.sh`), the replies and row logs (`head-q.jsonl`, `h.jsonl`) and the diff
(`candidate-h.diff`) are in the same directory as G's; the brain image was rebuilt from HEAD after H.

**Result.** The task is declined. Only removing the exchange from the pool moved L, and that
costs every draw of a repeated question whose answer only that exchange holds. Narrowing the drop
to a chat holding an unanswered handoff moves the same cost into that chat, since no memory says
whether a question refers to its own chat. The defect needs the same follow-up asked word for word
in another chat, and the answer it repeats is the deep model's own answer to the same question.
