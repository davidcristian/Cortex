# Readings: a reply that repeats its text across a tool call

How often a round of the tool loop (`stream_tool_loop` in `tool_loop.py`) that follows a call
begins with a sentence an earlier round of the same reply already wrote. Each round's text is
streamed to the person as it is written, so a repeat reaches the overlay and the chat's stored
assistant message.

## Rows and rule, 2026-10-30

Written before the baseline was drawn, for a check in the loop that drops a repeated opening
sentence. The rig is the one of [forget-request-wordings.md](forget-request-wordings.md#thirteen-more-wordings-rows-and-rule-2026-10-30):
the `cortexn11` stack over `Converse`, a new chat for each draw, every card approved, `memories`
empty at each draw's start, and every row a draw wrote deleted after it.

| Row | Message | Draws |
| --- | --- | --- |
| W04 | `What's the capital of Australia? And forget my phone number 0612345678 while you're at it.` | 15 |
| T01 | `Please remember this: my locker code is 7319. Also, which folders can you read?` | 10 |
| T02 | `Answer in one sentence first: what is 17 times 23? Then tell me which folders you can read.` | 10 |
| T03 | `What's the capital of Australia? And also tell me which folders you can read.` | 10 |

- The driver splits the text deltas a draw receives at each `tool_activity` event, so each piece
  is one round's text. A draw is a calling draw when it receives a `tool_activity` event. A
  calling draw repeats when a round after the first begins, after white space, with a sentence
  that an earlier round's text holds word for word.
- The baseline is the build of the commit that records the baseline for a removal claimed with
  no forget call. If W04 and T01 together repeat in fewer than 3 draws, W04 is drawn 15 more
  times. Fewer than 3 repeating draws in all is no live result, and no change of the loop ships
  on these rows. T02 and T03 were added after the first W04 and T01 draws and before any draw of
  their own, as rows whose first round is more likely to write text before its call; the same
  threshold of 3 applies to the four rows together.
- A change ships when the same rows and counts repeat in 0 draws, and every calling draw still
  shows the text its first round wrote. Its unit tests over fakes include a round that repeats an
  earlier sentence later in its text, which is kept. The candidate build may also hold the note
  for a removal claimed with no forget call, which the brain appends after the loop ends and so
  changes no round's text.

## Baseline, 2026-10-30

Run log `base942.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/def04344-43c5-4abe-b022-0038411a4a36/scratchpad/slot6/`,
the SM clock between 0.57 and 0.67 of its maximum at each batch's start and end. W04 was drawn
30 times, since W04 and T01 repeated in fewer than 3 of their first 25 draws.

| Row | Draws | Calling draws | With text before the call | Repeating |
| --- | --- | --- | --- | --- |
| W04 | 30 | 13 | 5 | 4 |
| T01 | 10 | 10 | 0 | 0 |
| T02 | 10 | 1 | 1 | 0 |
| T03 | 10 | 3 | 0 | 0 |

So 4 of 60 draws repeat, which is a live result. Each repeating draw's first round wrote "The
capital of Australia is Canberra." beside its `forget_memories` call, and its second round began
with the same sentence; in the fifth W04 draw with text before its call, the second round wrote
the sentence at its end instead. A draw repeats only when its first round writes text, and the
cortex wrote none before the call in 21 of the 27 calling draws.

The cause is in the cortex's chat template. llama-server's `/apply-template` renders a call
message that has text as the call, its result, then the text and the end of the model's turn, so
the next round starts after a turn that already answered. A call message with no text renders
with the turn still open after the result.

## The candidate, 2026-10-30

The candidate holds a round's text in `OpeningHold` (`round_opening.py`) until its first sentence
ends and drops that sentence when an earlier round of the reply streamed it word for word. Run log
`cand942.jsonl` in the same directory as the baseline, drawn after the seeded removal draws on
the same build, the SM clock at 0.59 of its maximum before them and 0.60 at the end.

| Row | Draws | Calling draws | With text before the call | Repeating |
| --- | --- | --- | --- | --- |
| W04 | 30 | 10 | 1 | 0 |
| T01 | 10 | 10 | 0 | 0 |
| T02 | 10 | 0 | 0 | 0 |
| T03 | 10 | 5 | 0 | 0 |

The change ships: the same rows and counts repeat in 0 draws, and every calling draw shows the
text its first round wrote. The live exposure is small, since only 1 candidate draw wrote text
before its call, against 6 in the baseline. Replaying the recorded rounds of the 4 repeating
baseline draws through `OpeningHold` drops each repeated sentence and leaves the rest of the round.
In one of the 6 seeded W04 draws of
[forget-request-wordings.md](forget-request-wordings.md#a-removal-claimed-with-no-forget-call-the-candidate-2026-10-30),
which ran on the same build, the first round wrote two sentences before its call and the reply
shows the second one twice, so a second round that repeats more than its first sentence still
shows the rest
([R-949](../refinements/tasks/949-a-round-can-repeat-more-than-one-sentence-of-an-earlier-round.md)).
