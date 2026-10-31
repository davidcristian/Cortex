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

## The form of the call message: rows and rule, 2026-10-31

Written before any draw, for
[R-947](../refinements/tasks/947-the-cortex-template-ends-the-turn-after-a-call-message-s-text.md)
and R-949. The question: does the form in which a call message sends its text change how often
the next round writes that text again, and what does each form cost the next round?

The rig is the `cortexn12` stack's cortex (gemma-4-12B, llama-server build `b12004`). A recording
proxy between the brain and the server captured the second-round requests of real W04 and T03
draws: the system message, the 18 tools and the tool results, with no sampling field and no
`max_tokens`. Each draw sends one such request directly to the server with only the user message
and the first round's text changed, and adds `max_tokens` 1500 as a limit on the rig. So
`OpeningHold` does not act on these rounds, and every draw has text before its call, which only 6
of 27 calling draws of the first baseline had.

| Form | What is sent | How the prompt ends, from `/apply-template` |
| --- | --- | --- |
| K | The text in the call message's `content`, which is what ships | call, result, text, `<turn\|>`, thought channel |
| O | The call message with empty `content` | call, result, thought channel |
| S | The text as an assistant message of its own before an empty call message, with the stock template | text, call, result, thought channel |
| T | K's render with `<turn\|>` removed, as an override template would write it, sent to `/completion` | call, result, text, thought channel |
| KR | K's render sent to `/completion`, the control for T's route | as K |

| Row | User message | First round's text | Call | Draws per form |
| --- | --- | --- | --- | --- |
| A1 | W04's message | `The capital of Australia is Canberra.` | `forget_memories`, nothing forgotten | 20 |
| A2 | W04's message | The same, then `I have also removed the phone number 0612345678 from my memory as you requested.` | `forget_memories`, nothing forgotten | 20 |
| A3 | T03's message | `The capital of Australia is Canberra.` | `list_allowed_directories` | 20 |
| L1 | `Pick a random whole number between 1000 and 9999 and tell me what it is. Then tell me which folders you can read, and after that tell me the number again.` | `My number is 4827.` | `list_allowed_directories` | 15 |

L1 cannot separate the forms: in its first 3 draws on O, whose prompt does not hold the number,
the model wrote 4827 every time, so that number is one it picks by itself. L2 replaces it for
`kept` from the fourth round of the first batch on, before any draw of its own: the same user
message, with the first round's text `My number is 1063.`, 15 draws per form. L1's draws are kept
and no rule reads them.

A4 was added after the first 35 draws of the first batch and before any draw of its own. A2's
tool result contradicts its second sentence, and in the draw R-949 records the forget had deleted
a row, so A4 sends A2's text with the real result `forgot 1 remembered exchanges; no remembered
exchange contains that text now.` and the note the dispatcher adds. It is drawn 20 times on K, and
on a form that ships if one does, in a batch of its own.

KR is drawn on A1 and L2 only. The draws go round robin over row and form, so a change of clock
falls on every form alike. Each second round is counted as:

- `opens`: its text begins, after white space, with a sentence the first round holds word for word.
- `both`: on A2 and A4, its first two sentences are both ones the first round holds word for word.
- `any`: any of its sentences is one the first round holds word for word.
- `again`: on A1, A2, A3 and A4, its text has `Canberra` in any wording.
- `reported`: on A3 and L2 its text has `/projects`; on A1, A2 and A4 its text speaks of the phone
  number or of forgetting, removing or storing.
- `kept`: on L2 its text has `1063` and no other four digit number. This is the condition for the
  context the next round needs. A form that hides the first round's text cannot name the number
  except by chance.
- `empty`: it has no text and no call. `recall`: it calls a tool again.

The rule for R-947:

- **Null result.** K's `opens` over A1, A2 and A3 together is under 3 of 60. Then these rows do
  not separate the forms at this build, no form ships, and the task records the count.
- **A form ships** only when, over A1, A2 and A3 together, its `opens` is at most a quarter of K's
  and its `again` at most three quarters of K's; its A3 `reported` and its L2 `kept` are each at
  most 2 draws below K's; and its `recall` and its `empty` are each at most 2 draws above K's. A
  second batch of the same rows and counts must pass the same rule. Then W04 30 and T03 10 are
  drawn over `Converse` on a build with the form: 0 draws repeat, and every calling draw shows the
  text its first round wrote.
- **S before T.** When both pass, S ships, since it needs no template file. T's counts are read
  against KR, not K, when KR and K differ by more than 3 draws on a count.
- **The hold.** `OpeningHold` is removed only when the shipping form's `opens` is 0 in both
  batches; otherwise it stays as it is.

The rule for R-949, over the A2 and A4 draws of whichever form the loop sends after the rule above:

- **Null result.** Under 3 of the 40 draws have `both`; 20 more of each are drawn, and under 3 of
  80 leaves `OpeningHold` unchanged and the task open with the count.
- **The fix ships** when at least 3 draws have `both`, and replaying the recorded second rounds in
  small pieces through the old and new `OpeningHold` shows: the new one leaves no reply whose
  second round opens with a sentence of the first, and it changes no reply whose second round did
  not open that way. Its unit tests keep a repeated sentence that follows a new one.

Two more rows, written after the first batch ended and before any draw of their own:

- **The live check of the fix.** A build with the new `OpeningHold` draws W04 15 times and seeded
  W04 10 times over `Converse`, with the driver of the first baseline. It passes when every
  calling draw shows its first round's text and no later round opens with a sentence an earlier
  round wrote word for word. A failure stops the fix.
- **A replication of K's `kept`.** L3 and L4 send the first round's text `My number is 6158.` and
  `My number is 2946.` with L2's user message, 15 draws each on K and S. It decides only whether
  the K result of L2 is filed as a defect: at least 3 draws over L3 and L4 on K name another
  number, against at most 1 on S. Under that, K's `kept` on L2 is recorded as noise.

## The form of the call message: result, 2026-10-31

Run log `batch1.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot1/`.
The SM clock read between 0.22 and 0.66 of its maximum at the batch's readings.

`/apply-template` on this build renders K's end as `<tool_response|>The capital of Australia is
Canberra.<turn|>`, a line break and `<|channel>thought`. The generation prompt opens the thought
channel with no new `<|turn>model`, so the next round starts outside any turn. With two call
messages, only the last one's text ends the turn; an earlier one's text stays in the turn after
its result. The text is never where the model wrote it, before the call, except in S.

| Form | `opens` A1 | `opens` A2 | `opens` A3 | `opens` of 60 | `again` of 60 | `reported` A3 of 20 | `kept` L2 of 15 | `reported` L2 of 15 | `recall` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| K | 11 | 19 | 2 | 32 | 34 | 20 | 11 | 15 | 1 |
| O | 20 | 20 | 20 | 60 | 60 | 20 | 0 | 15 | 0 |
| S | 16 | 19 | 3 | 38 | 38 | 18 | 15 | 11 | 2 |
| T | 18 | 20 | 10 | 48 | 49 | 20 | 13 | 15 | 0 |
| KR, A1 and L2 only | 14 | | | | | | 14 | 15 | 0 |

No draw is `empty`. One KR draw on A1 reached the rig's limit while still in its thought.

**No form stops the repeat, so no form ships.** K's 32 of 60 is a live result, and a passing form
needed at most 8 `opens`. Leaving the text out is the worst form: the next round opens with the
sentence on all 60 draws, because the model no longer sees that it answered and answers the
question again, and all 15 L2 draws name a number other than the one the person already read. A
turn kept open does not help, with the text after the result (T, 48) or before the call (S, 38).
The row matters more than the form: K opens with the sentence on 19 of 20 A2 draws and 2 of 20 A3
draws. The call message stays as it is, and `OpeningHold` stays, since no form reaches 0.

What K's closed turn does cost is thought. The median second round took 0.42 of K's time on O,
0.33 on S, 0.24 on T and 0.91 on KR, and its median thought was 706 characters on K, 307 on O, 220
on S and 0 on T, where 61 of 79 draws have no thought. Only a round after text written before its
call pays this, which was 6 of 27 calling draws in the first baseline. S's price is `reported`:
4 of its 15 L2 draws give the number and leave the folders out.

K's 11 of 15 on L2 was a surprise, as the other 4 draws name another number (4827, 4829, 7482,
4729) after the first round said 1063. It did not repeat. In the replication written above, L3 and
L4 on K name another number in 1 of 30 draws and on S in 0 of 30, under the 3 the rule asks for,
so it is recorded as noise. S's `reported` on those rows is 28 of 30, against 30 of 30 on K.

## More than one repeated sentence: result, 2026-10-31

K stays, so R-949's rule reads K's draws: `both` is 6 of 20 on A2 and 14 of 20 on A4, which is 20 of
40 and a live result, so the fix ships. `OpeningHold` now drops each opening sentence an earlier
round streamed and streams from the first one that is new.

Replaying the recorded second rounds in pieces of 1 to 5 characters: over K's 99 rounds the old
hold leaves an opening repeat in 20 and the new one in 0; over all 375 rounds of the first batch
and A4, in 22 and in 0. The new hold changes no round that did not open with a repeat. On K's A2
and A4 rounds, a reply showing a sentence twice falls from 20 of 40 to 0 of 40. The hold's tests
keep a repeated sentence that follows a new one.

The live check passes, with a small exposure, so the replay is the main evidence. Run log
`live.jsonl` in the same directory, the SM clock at 0.21 of its maximum before the draws and 0.45
after them. W04 had 15 draws, 5 calling and none with text before its call. Seeded W04 had 10
draws, 4 calling and 2 with text before the call, one of those two sentences. No later round opens
with a sentence an earlier round wrote, and each of the 2 shows its first round's text.

All 20 A4 rounds open with the first sentence. The 6 without `both` go on with the second sentence
in other words, such as `I have also removed the phone number 0612345678 from my memory.` against
the first round's `... from my memory as you requested.`. The hold reads word for word, so it keeps
them and the reply says the same thing twice
([R-960](../refinements/tasks/960-a-round-can-repeat-an-earlier-sentence-in-other-words.md)).

## A round that loops on an earlier sentence: result, 2026-10-31

A fixed round writing an earlier round's line 400 times ran to its end with nothing shown, since the
hold dropped every copy before the repeat watch read it. A sentence back a second time in one round
now ends the hold, and the same round ends at the watch's third copy. Replaying the 449 later rounds
of `live`, `batch1`, `cap-w04`, `cap-t03` and `cap-t03b` through both holds changes none of them.
