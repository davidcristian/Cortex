# Readings: the forget tool on a plain English statement of a fact

How `forget_unrequested` (`forget_unrequested.py`) reads a message that states a fact in English
and asks nothing, such as `My locker code at the pool is 7319.`, and what a store turn of that
message does when the model calls `forget_memories` unasked. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s; the narrowed reader is measured in
[forget-refusal-other-languages.md](forget-refusal-other-languages.md).

## The store turn on both builds: rows and the rule

Written 2026-11-13 before any draw. A call the reader refuses is not counted by
`TaintLedger.name_forget`, so it does not withhold the exchange from memory; a call it keeps runs,
matches no row and withholds the exchange (`memory_withheld`). The start build `cec7c748f` refuses
the tool on this message and HEAD `c09bed089` keeps it.

Each draw empties `memories`, sends `My locker code at the pool is 7319.` in a new chat with every
card approved, and reads the rows after. The start build is the stack brain (port 23051) and HEAD
is `cortexn21-brain-s6head` (port 23066, built from `c09bed089`), both memory tools only, through
the recording proxy. Eight draws per build, alternating. A build with fewer than two draws that
call the tool gets four more, a cap of twelve.

- **The narrowed reader is the cause** when the first requests of the two builds are the same
  apart from the clock, every start build draw that calls the tool has the call refused and stores
  the locker row, and every HEAD draw that calls it runs the call and stores no row.
- **The change is cleared** when a start build draw that calls the tool stores no row, or a HEAD
  draw that calls it stores the row.
- A draw with no forget call decides nothing and is counted apart; it is expected to store the
  row on both builds. The call rate per build is a separate count, from the same first request.

## The store turn on both builds: what was drawn

Drawn from 03:49 to 03:51 on 2026-11-13, proxy log lines 453 to 474, SM clock 0.58 of
`clocks.max.sm` between draws. The 16 first requests were byte for byte the same, so the two
builds differ only after a call.

| Build | Draws | Draws with a forget call | The call | Locker row stored |
| --- | --- | --- | --- | --- |
| start `cec7c748f` | 8 | 2 | refused, 2 of 2 | 8 of 8 |
| HEAD `c09bed089` | 8 | 4 | ran and matched nothing, 4 of 4 | 4 of 8, none after a call |

**Result: the narrowed reader is the cause.** Each HEAD call withheld the exchange, and its reply
held the note that nothing in the message was kept. The calls sent the store turn's own text: the
whole message, `locker code at the pool is 7319`, `7319` and `locker code` at HEAD, and
`locker code at the pool is 7319` and `7319` at the start build. Draw logs `draw-sep.log` and
`draws-sep.jsonl`, scripts `draw.sh`, `summ.py` and `firstreq.py`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot6/`.

## The fix on the live stack: rows and the rule

Written before its draw. The working tree with `_states_in_english` runs as
`cortexn21-brain-s6fix` (port 23067, memory tools only), eight draws of the same store turn, each
on emptied `memories`. The rule: every draw that calls the forget tool has the call refused and
stores the locker row, and every draw stores it. A draw with no call is counted apart.

## The fix on the live stack: what was drawn

Drawn from 03:53 to 03:54 on 2026-11-13, proxy log lines 476 to 486, SM clock 0.58. The drawn
build had the reader before its value was bounded to four words, which reads this message the
same way.

| Build | Draws | Draws with a forget call | The call | Locker row stored |
| --- | --- | --- | --- | --- |
| `s6fix` | 8 | 3 | refused, 3 of 3 | 8 of 8 |

**Result: the rule holds.** Log `draw-fix.log`, the rows in `draws.jsonl`, in the slot directory
above.

## Replay through the start build, HEAD and the fix

Taken 2026-11-13 with no last reply over 33,028 strings: every test string of `brain/`, every
backticked text of `docs/`, the last user message of every request in the night's proxy log, and
61 messages in twelve languages (Italian, Portuguese, Dutch, Polish, Catalan, Norwegian and Finnish
among them).

| Build | Refused |
| --- | --- |
| start `cec7c748f` | 27,474 |
| HEAD `c09bed089` | 830 |
| the fix | 856 |

26 strings change against HEAD, every one now refused and every one refused at the start build
too. They are the English statements of a fact among the strings, such as
`My locker code at the pool is 7319.`, `My phone is 0721 555 019.`,
`my Visa is 4111 1111 1111 4242`, `My number is 1063.` and three more like it,
`My sister is vegan.`, `my dog is Rex`, `my bank's name is Askari`,
`Her birthday was on May 3. My code is 7319!` and `My alarm code is now 5528.`. No string in the
twelve languages changes other than `My sister is vegan.`, and no string HEAD refuses is kept.
`My PIN is 4412 (keep it nowhere).`, `My PIN is 4412 - keep it.`,
`My kode is verkeerd en vee dit dadelik weg.` and `My code is 7319?` keep the tool.
Scripts `replay.sh`, logs `start.json`, `head.json`, `new.json` and `diff_head_new.txt` in the slot
directory above, with the collect, run and diff scripts of `slot3/` beside it.

## A statement while a forget is open

A statement can answer the assistant's own question in a forget flow, as in `Cancel the code I
gave you.`, then `Which code is it?`, then `My locker code is 4242.`. Neither reply reader names
`cancel`. `_states_in_english` counts a statement only when no message of the person in the last
two exchanges holds what `_CAN_RETRACT` or `_misspells_forgetting` reads in the message itself (a
word that can retract, a negation, a near `forget` or a letter outside `a-z`). The tool loop reads
those two messages from the chat as `earlier` and `before` (`_earlier_asks` in `tool_loop.py`),
skipping the messages of the turn itself, since a handoff's working list ends with the cortex's
calls for that turn after the person's message. What the last reply asks is not read. A request to remember or a question after such a message is
still refused, unless the last reply or `earlier` names forgetting.

A build that counted a statement only after a last reply holding no `?` was replayed 2026-11-13
through HEAD `c0e02329e` and that build over 33,201 strings (the sources above) and the 165 turns
of the night's proxy log, each with its own last reply and earlier message.

| Read | HEAD refused | That build refused |
| --- | --- | --- |
| each string, no last reply | 881 | 881 |
| each string after `Which one do you mean?` | 881 | 853 |
| each recorded turn | 46 | 46 |

The 28 strings that change are the English statements of a fact the reader refuses alone, such as
`My phone is 0721 555 019.`, `My sister is vegan.` and `my dog is Rex`, kept after the question.
No string or turn changes from kept to refused. Scripts `replay.py` and `cmp.py`, logs
`head.json`, `new.json` and `diff_head_new.txt`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot10/`.

## A statement after a courtesy question: rows and the rule

Written 2026-11-13 at 06:47, before the draw. The build is `cortexn21-brain-s11fact` (port 23112,
the brain code of HEAD `62fbefc2c`, memory tools only). Each of six draws empties `memories`,
sends `Hi! How are you today?` in a new chat, then `My locker code at the pool is 7319.` in the
same chat, every card approved. The form is reproduced when a first reply holds a `?` and the
second turn's first request lists `forget_memories`; it is cleared when no such request lists it.
Forget calls and the locker row stored after are counted apart and fail nothing.

## A statement after a courtesy question: what was drawn

Drawn from 06:47 to 06:48 on 2026-11-13, proxy log lines 875 to 896, SM clock 0.58 and 0.59 of
`clocks.max.sm` before and after.

| First replies holding `?` | Second requests listing the tool | Forget calls | Locker row stored |
| --- | --- | --- | --- |
| 6 of 6 | 6 of 6 | 4 of 6, each matching nothing | 2 of 6, none after a call |

**The form is reproduced.** Each first reply ended with a question such as `How can I help you
today?`, which that build's statement reader read as a question the statement may answer. Each call
withheld the exchange, as in the draws above without the refusal. No brain note holds a `?` (179
note forms), so only the model's own text counts. The script `draw.sh`, the logs `draw.log` and
`draws.jsonl` and `summ.py` are in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot12/`.

## The open forget check: replay

Taken 2026-11-13 through HEAD `868cd33d8` and the open forget check over 33,382 strings (the
sources above, the test strings of the tree and every user message of the proxy log to line 896)
and the 198 turns of that log, each with its own last reply, `earlier` and `before`.

| Read | HEAD refused | The check refused |
| --- | --- | --- |
| each string, no last reply | 919 | 919 |
| after `Hi! How are you today?` and a reply asking `How can I help you today?` | 875 | 919 |
| after `Which one do you mean?` | 875 | 919 |
| after `Cancel the code I gave you.` and `Which code is it?` | 875 | 875 |
| after `Cancel the code I gave you.`, `The alarm one.` and a question | 875 | 875 |
| each recorded turn | 52 | 55 |

The 44 strings that change after either question are the English statements of a fact the reader
refuses alone, such as `My locker code at the pool is 7319.`, `My alarm code is now 5528.` and
`my wifi is plum`; each is refused alone by both builds. The three turns that change are two of
the courtesy chains drawn above (their six draws hold two distinct replies) and
`My alarm code is now 5528.` after `My alarm code is 4826.`, whose reply asks
`Is there anything else you'd like me to help you with?`. No string or turn changes from refused
to kept. Scripts `collect.py` and `replay.py`, logs `head.json`, `work.json` and
`diff_head_work.txt`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot13/`.

## The open forget check on the live stack: rows and the rule

Written 2026-11-13 at 07:09, before the draw. The build is `cortexn21-brain-s13open` (port 23131,
the working tree with the check, memory tools only), through the recording proxy.

- **Courtesy chains**, six draws: empty `memories`, send `Hi! How are you today?` in a new chat,
  then `My locker code at the pool is 7319.` in the same chat, every card approved. The check holds
  when every forget call of the second turn is refused with `FORGET_UNREQUESTED` and every draw
  stores the locker row. It fails when a call runs or a draw stores no locker row.
- **The forget flow**, three draws: empty `memories`, store `Remember that my alarm code is 5528.`
  and `Remember that my locker code is 4242.` in two chats, then send `Cancel the code I gave
  you.` in a new chat with every card denied. When that reply asks which code and calls nothing,
  send `My alarm code is 5528.` with every card approved. The check holds when every forget call
  of that turn runs and its card deletes the alarm row and keeps the locker row. It fails when such
  a call is refused. A draw that calls the tool on the first message, or makes no call on the
  second, decides nothing and is counted apart; with fewer than two deciding draws, three more.

## The open forget check on the live stack: what was drawn

Drawn from 07:09 to 07:14 on 2026-11-13, proxy log lines 898 to 992, SM clock 0.58 and 0.65 of
`clocks.max.sm` before and after.

| Flow | Draws | Deciding draws | Forget calls on the deciding turn | Rows after |
| --- | --- | --- | --- | --- |
| courtesy chain | 6 | 6 | 2, refused 2 of 2 | locker row stored 6 of 6 |
| forget flow | 6 | 2 | 2, run 2 of 2 | alarm row deleted, locker row kept, 2 of 2 |

**Result: the check holds.** In four forget flows the first message called the tool and its card
was denied, so they decide nothing. In the two that asked first (`Which code would you like me to
forget?`), the statement kept the tool and the approved card deleted only the alarm row. The
scripts `draw.sh` and `summ.py`, the logs `draw.log` and `draws.jsonl`, are in the slot directory
above.
