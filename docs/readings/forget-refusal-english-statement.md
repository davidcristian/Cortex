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

## A statement after a reply asking a question

A statement can answer the assistant's own question in a forget flow, as in `Cancel the code I
gave you.`, then `Which code is it?`, then `My locker code is 4242.`. Neither reply reader names
`cancel`, and a forget asked two turns back is out of `earlier`, so the statement class refused the
tool there. `_states_in_english` now counts a statement only when the model's text of the last
reply holds no `?`; a request to remember or a question after one is still refused. No draw was
taken: the change only keeps the tool.

Replayed 2026-11-13 through HEAD `c0e02329e` and the fix over 33,201 strings (the sources above)
and the 165 turns of the night's proxy log, each with its own last reply and earlier message.

| Read | HEAD refused | The fix refused |
| --- | --- | --- |
| each string, no last reply | 881 | 881 |
| each string after `Which one do you mean?` | 881 | 853 |
| each recorded turn | 46 | 46 |

The 28 strings that change are the English statements of a fact the reader refuses alone, such as
`My phone is 0721 555 019.`, `My sister is vegan.` and `my dog is Rex`, now kept after the
question. No string or turn changes from kept to refused. Scripts `replay.py` and `cmp.py`, logs
`head.json`, `new.json` and `diff_head_new.txt`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot10/`.
