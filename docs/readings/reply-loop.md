# Readings: a reply that repeats one line

What the cortex writes once it starts repeating itself, and whether a sampling setting or a check
on the streamed reply ends the loop before the length limit. This record holds the rig, the rows
and the pass rule, written before any baseline row was drawn.

## What bounds a looping reply today

Read on 2026-10-13 from the test stack's cortex server (`/props`, build `b11552-23b0202a1`) and the
tree:

- The brain sends no sampling field, and with `CORTEX_REPLY_MAX_TOKENS` at its default 0 it sends
  no `max_tokens`, so a reply is bounded only by the slot's context: 16384 tokens less the prompt,
  5,374 tokens on the rig's state below, so about 11,000 tokens of reply.
- The server's defaults have both repetition samplers off: `repeat_penalty` 1.0 and
  `dry_multiplier` 0.0. The others are `temperature` 1.0, `top_k` 64, `top_p` 0.95, `min_p` 0.05
  and `n_predict` -1. The model host starts the cortex tier with no sampling flag.
- In the brain, `REDUNDANT_MSG` refuses an exact repeated tool call, and nothing reads repeated
  text. The stall ceiling sees only silence, and the token cap of
  [ADR-0048](../adr/ADR-0048-generation-bounds.md) applies to a delegated run, not to the cortex.

The probe row of the [cut off tool call](tool-call-cut-off.md#results) rows looped in the reply,
not in `reasoning_content`: its 3,764 words arrived as text from 21.4 s into the turn, and they
open with the model's own plan, "The user wants to know who sings in week 2 according to the
`choir-rota.txt` file.", a trace written as reply text. Two lines then alternate 357 times each.

## The rig

A replay of that probe row at the engine. One cut off read row was drawn with a packet capture
beside the model host, which recorded every request the brain sent: the system prompt, the 20 tool
definitions and each tool result as the model reads it. The rig's state is that request with the
probe row's own calls: `list_allowed_directories` and `list_directory` succeed, then
`read_text_file`, `read_file` and `read_text_file` fail as unknown tools, a fourth read is refused
as an exact repeat, and `list_directory` fails as an unknown tool. Each draw posts the state to the
cortex server, not streamed, with `max_tokens` 1536 to bound its cost.

- **Without a prefill** the next completion is a tool call or a short apology: 0 of 3 probe draws
  looped.
- **With the probe row's first reply sentence as an assistant prefill** (it ends "I'll try to read
  it again using `read_text_file`."), 3 of 3 probe draws looped to 1536 tokens, one line repeated
  18 to 47 times in each. The rig therefore measures what happens once the model has started
  writing its plan into the reply, the state the probe row shows. It does not measure how often a
  turn reaches that state.

Two controls use the same system prompt and tools:

- **Tool call control**: the state after `list_directory` succeeds, before any read. A draw passes
  when it calls `read_text_file` or `read_file` with the path `/projects/choir-rota.txt`.
- **Format control**: a new conversation whose message is "Without using any tool, write twelve
  lines, one per month from January to December, each exactly in the form `<Month>: choir practice
  on the first Tuesday at 7 pm`." A draw passes when its reply holds all twelve lines in that form.
  It tests a sampling setting against a reply that must repeat its own words.

## The rows

- **Baseline**: 10 rig draws, 10 tool call control draws and 10 format control draws, at the
  server's defaults.
- **Candidate A, DRY**: the same 30 draws with `"dry_multiplier": 0.8` in each request, which is
  what a cortex tier started with `--dry-multiplier 0.8` applies to every request. The other DRY
  values stay at the server's defaults (base 1.75, allowed length 2).
- **Candidate B, a repeated line check**: read off the baseline draws, with no new draw. It ends a
  reply as soon as one line of at least 20 characters, holding at least one letter, arrives for
  the third time, and appends a note saying the reply was stopped because it repeated itself. Its
  rows are where it stops each rig draw, in words of reply counting the prefill, and whether it
  stops any control draw of either phase.
- SM clock read after each phase with `nvidia-smi`.

## How a draw is classed

- **Loops**: one line of the reply appears three times or more, or the draw stops at its 1536
  token limit.
- **Calls**: the draw ends with a tool call.
- A control draw passes or fails as its control defines above.

## The pass rule

- **The defect reproduces** on the rig when at least 7 of the 10 baseline rig draws loop.
  Otherwise neither candidate is judged on this rig.
- **Candidate A ships** as a flag of the cortex tier when at most 2 of its 10 rig draws loop, all
  10 of its tool call control draws pass, and its format control passes no more than one draw
  fewer than the baseline's.
- **Candidate B ships** when it stops every looping baseline rig draw but at most one within the
  first 400 words of reply, and stops no control draw in either phase.
- **When both pass, candidate B ships**: it changes only a reply that already repeats, and it reads
  the stream the brain already has, on every tier and engine. Candidate A is then filed as its own
  task and measured again with B in place.
- Any other result changes nothing, and the rows are recorded here.

## The second rig

The first rig's baseline did not reach the rule's 7 of 10 (see Results), so a second rig primes
the loop further, with its own rule written before its baseline.

- **State**: the first rig's state, with the probe row's first 25 reply lines as the prefill in
  place of its first sentence, 237 words that end "Actually, I'll try `read_file` since
  `read_text_file` gave "unknown tool" (which is weird because it's in the list)." No line in them
  appears more than once, so a loop must still start in the draw.
- **Rows**: 10 baseline rig draws, then, if the defect reproduces, 10 rig draws for candidate A.
  Both controls are the first rig's, and their baseline is the one in Results; candidate A draws
  its 20 control draws again.
- **Classes and rule**: the first rig's, with one change: candidate B's bound is 400 words of
  reply after the prefill, not counting it.

## The third rule

Both rigs loop in about half of their draws once the plan is in the reply, under the 7 of 10 the
first rule needs, so this rule is sized for that rate. It uses the second rig and its controls,
and judges only draws made after it was written.

- **Baseline**: 20 rig draws at the server's defaults. **The defect reproduces** when at least 6
  of the 20 loop; otherwise neither candidate is judged.
- **Candidate A ships** when at most 1 of its 20 rig draws loops, all 10 of its tool call control
  draws pass and at least 9 of its 10 format control draws pass.
- **Candidate B ships** when, read off the baseline draws, it stops every looping draw but at most
  one before the draw's 1536 token limit, and stops no draw that does not loop and no control
  draw. The person then reads at most what one draw holds, about a seventh of what the context
  window allows.
- When both pass, candidate B ships and candidate A is filed as its own task, as in the first rule.

## The fourth rule

The three baselines together loop in 14 of 40 rig draws, about a third, so this rule is sized
from that rate. It compares both candidates on rows drawn in one night, all after it was written,
on the second rig and the first rig's two controls. A draw is classed as above, on its own text.

- **Rows, in this order**: 40 baseline rig draws and 20 baseline control draws (10 tool call, 10
  format) at the server's defaults; then, when the defect reproduces, 40 rig draws and 20 control
  draws with `"dry_multiplier": 0.8` in each request. SM clock read after each phase.
- **The defect reproduces** when at least 8 of the 40 baseline rig draws loop. At a true rate of a
  third, fewer than 8 happens about once in 80 baselines. Otherwise neither candidate is judged.
- **Candidate A ships** when its looping rig draws number at most a quarter of the baseline's,
  rounded down, all 10 of its tool call control draws pass, and at least 9 of its 10 format
  control draws pass. Shipping it adds `--dry-multiplier 0.8` to the cortex tier's argv in the
  model host.
- **Candidate B ships** when, read off the baseline draws, it stops every looping rig draw but at
  most one before the draw's token limit, and stops no rig draw that does not loop and no baseline
  control draw. It reads a rig draw as the turn holds the reply, the prefill followed by the draw.
  Shipping it ends the reply at that line and closes it with a note through `limit_notes` in
  `cortex_core/turn_output.py`, the path `REPLY_CAPPED_NOTE` takes.
- When both pass, candidate B ships and candidate A is filed as its own task, as in the first rule.
- Any other result changes nothing, and the rows are recorded here.

## The fifth rule

A line arriving a third time also ends a reply the person asked to repeat. In every looping
baseline draw of the fourth rule (read before this rule was written) one block of one to four
lines comes back to back; a request repeats a line the message names, and a song or a list brings
a line back with other lines between. Four shapes are compared. A line is *held by the message*
when, lowercased with each run of other characters than letters and digits read as one space, it is
a run of whole words of the person's message. Lines count as before: at least 20 characters with
a letter.

- **A**: a line arrives for the eighth time. **B**: a line not held by the message arrives for the
  third time. **D**: A and B together, the eighth arrival of a line not held by the message.
- **C**: the last non-blank lines are three back to back copies of one block of one to four lines,
  and the block has a counted line not held by the message.
- **Request rows**, drawn after this rule at the server's defaults with `max_tokens` 2048, five
  draws each, on the format control's state with its message replaced: five copies and ten copies
  of "Remember to bring your sheet music to practice." one per line; a song of three verses, each
  followed by the same four-line chorus; and a reminder for each month, the month on one line and
  the same sentence of the model's own under it. A row judges only when at least 3 of its 5 draws
  repeat a counted line at least three times; otherwise no shape is judged.
- **A shape passes** when, read off the fourth rule's baseline (the rig draw after its prefill, the
  rig's message as the person's), it stops every looping rig draw but at most one before its token
  limit, no other rig draw, no control draw and no request draw.
- **The first passing shape in the order C, D, B, A ships** in `RepeatWatch`: C reacts only to
  copies with nothing between them, the shape every loop above has. No pass changes nothing.
- **The list row again**: its first 5 draws repeated their sentence in 1, so it judged nothing. Its
  5 draws are made again after this line was written, with the message asking for one sentence
  written once and repeated word for word under every month; the rest of the rule stands.

## Results

**2026-10-13, the first rig's baseline**, 30 draws on the current tree at the server's defaults.

| Draws | Result |
| --- | --- |
| rig | 4 of 10 loop, each to the 1536 token limit, the most repeated line 20 to 83 times; the other 6 write 175 to 407 words of plan as reply text, the prefill included, and then call `read_text_file` |
| tool call control | 10 of 10 pass |
| format control | 10 of 10 pass, every line exact |

4 of 10 is under the 7 the rule needs, so **the defect does not reproduce** on the first rig and
neither candidate is judged on it. Read off the same draws for the record, candidate B would have
stopped the 4 loops at 384, 430, 488 and 722 words of reply, counting the prefill, and stops none
of the other 6 rig draws or any control draw. The control driver first kept the call names
without their arguments, so the 10 tool call control draws above are a second draw that kept
both. SM clock 0.63 of `clocks.max.sm` after the phase.

**2026-10-13, the second rig's baseline**, 10 draws: 5 of 10 loop, each to the 1536 token limit,
the most repeated line 26 to 44 times; the other 5 add 17 to 45 words of plan and then call
`read_text_file`. 5 of 10 is under 7, so **the defect does not reproduce** under the first rule and
neither candidate is judged. For the record, candidate B would have stopped the 5 loops at 338 to
444 words after the prefill, 1 of them within the 400 the first rule asks for, because the loop's
wording drifts for a few lines before one line settles. SM clock 0.62 of `clocks.max.sm`.

**2026-10-13, the third rule's baseline**, 20 draws of the second rig: 5 of 20 loop, each to the
1536 token limit, the most repeated line 14 to 63 times; the other 15 call `read_text_file` after
at most 125 words of plan. 5 is under the 6 the rule needs, so **the defect does not reproduce**
under the third rule either, candidate A was not drawn, and neither candidate is judged. SM clock
0.58 of `clocks.max.sm`.

Across the three baselines, 14 of 40 rig draws loop, about a third, and each one runs to its
token limit. Read off the same draws and not judged by any rule, candidate B stops all 14 loops
before that limit, 267 to 677 words after the prefill, and stops none of the 26 draws that do not
loop and none of the 20 control draws. A rule that needs a reproduction rate near a half does not
fit a rig that loops about a third of the time; the next rule is sized from that third.

**2026-10-14, the fourth rule's rows**, 120 draws on a new test stack with the same server build
and the same defaults read from `/props`, the second rig and both controls.

| Draws | Baseline | Candidate A, `"dry_multiplier": 0.8` |
| --- | --- | --- |
| rig | 22 of 40 loop, each to the 1536 token limit, the most repeated line 14 to 78 times; the other 18 call a read after 9 to 193 words of plan | 12 of 40 loop, each to the token limit with no line more than 5 times, as the wording drifts; the other 28 call a read |
| tool call control | 10 of 10 pass | 10 of 10 pass |
| format control | 10 of 10 pass | 0 of 10 pass: each spends all 1536 tokens in `reasoning_content` and writes no reply |

22 of 40 is at least 8, so **the defect reproduces**. **Candidate A fails**: 12 loops is over a
quarter of the baseline's 22, and the format control shows DRY sampling breaking a reply that must
repeat its own words. **Candidate B passes**: read off the baseline, with the prefill and the draw
together, it stops all 22 loops, 213 to 512 words after the prefill, and stops none of the 18
other rig draws and none of the 20 control draws. A is not filed. Read off A's own rig draws, B
would stop only 9 of its 12 loops, since DRY keeps a drifting loop from repeating an exact line. SM
clock 0.58 to 0.66 of `clocks.max.sm` under load in the baseline phase, 0.60 to 0.71 in candidate
A's. Built into the brain on the test stack, B ended a live turn asking for five copies
of one line at the third, with its note, while a read of the choir rota and the twelve-month format
control ran as before. The fifth rule compares shapes that tell such a request from a loop.

**2026-10-14, the fifth rule's rows**, 25 request draws on the same stack and server build, read
with the fourth rule's 60 baseline draws. Words are after the prefill.

| Shape | Looping rig draws stopped | Other rig and control draws stopped | Request draws stopped: five copies, ten copies, song, list |
| --- | --- | --- | --- |
| A, eighth arrival | 22 of 22, at 243 to 552 words | 0 | 0, 5, 0, 5 |
| B, third arrival of a line the message lacks | 22 of 22, at 213 to 512 words | 0 | 0, 0, 5, 5 |
| C, three back to back copies of a block | 22 of 22, at 221 to 516 words | 0 | 0, 0, 0, 0 |
| D, eighth arrival of a line the message lacks | 22 of 22, at 243 to 552 words | 0 | 0, 0, 0, 5 |

Every row judges. Each copy draw wrote the line 5 or 10 times on lines of its own, each song draw
brought its four-line chorus back three times, and each draw of the second list row repeated one
sentence 12 times; the first list row did so in 1 of 5 draws, which A, B and D stop and C does not.
A line's third arrival, the fourth rule's B, stops all 20 request draws. **C passes** and ships in
`RepeatWatch`. Fed each draw in pieces of 7 characters, the built watch stops exactly the 22 looping
rig draws among the 80. With it in the brain, live turns for each request and the twelve-month
format control ran to their end with no note. SM clock 0.64 to 0.69 of `clocks.max.sm` after each
request row. A request to repeat a line the model makes up has its own rule, in
[requested repeats](reply-loop-requests.md).

Method: the capture and replay drivers in the run's scratch directory, against the test stack's
cortex server on `127.0.0.1:8080`.
