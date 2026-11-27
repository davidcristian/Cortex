# Readings: an open forget read from what the earlier turns did

How `forget_open` (`forget_open.py`) reads whether one of the chat's last two exchanges opened a
forget, so that an English statement of a fact after it keeps the forget tool, and what that does
on the live stack. The refusal it feeds is measured in
[forget-refusal-english-statement.md](forget-refusal-english-statement.md); the decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## What the store keeps of an earlier turn

The tool loop reads the chat from `working`, the history the turn engine and the deep phase load
through `SessionStore`. Of an earlier turn it holds the person's message (with the note
`attachment_note` appends after a picture), the reply as shown (with the brain's notes) and the
reply's `runs`: one `ToolRun` per tool call that was dispatched, with its name and whether it
succeeded. A declined card is a run. A call the brain refused by name (`FORGET_UNREQUESTED`,
`UNASKED` and the other `DispatchRefusal` values) yields no `StepOutcome`, so **the store keeps no
record of a refusal**. `forget_open` therefore reads three things per exchange: a run of
`forget_memories` or `forget_untrusted_memories`, a reply whose model text (`model_text`) names
forgetting, and a person message that `asks_to_forget` reads as a request to forget.

## Replay through HEAD and the deed reader

Taken 2026-11-13 through HEAD `859828aa4` and the deed reader over 33,396 strings (the strings of
the earlier replays) and the 206 distinct recorded first requests of the night's proxy log to line
992, each read with its own last two exchanges. Each condition puts the exchanges named before
every string; "Anything else" is the reply `Got it. Anything else I can help with?`.

| Read | HEAD refused | Deed reader refused |
| --- | --- | --- |
| each string, no exchange | 920 | 920 |
| after a courtesy question | 920 | 920 |
| after `Cancel the code I gave you.` and `Which code is it?` | 876 | 920 |
| the same, its forget call run | 876 | 0 |
| the same, the reply `Which code would you like me to forget?` | 0 | 0 |
| after `Look at this.` with a picture and a reply | 876 | 920 |
| after `Don't forget my dentist on Friday.` and "Anything else" | 0 | 920 |
| after `I forgot my keys.` and "Anything else" | 0 | 920 |
| after each of seven more near misses and "Anything else" | 876 | 920 |
| after `Get my phone number out of there.` and `Which one, work or personal?` | 920 | 920 |
| each recorded turn | 56 | 55 |

The 44 strings that change after a near miss are the English statements of a fact, now refused, as
alone. After a turn that ran a forget call every string keeps the tool, as HEAD does after a reply
naming forgetting. Three recorded turns change. Two requests to remember in Spanish and Romanian
are now kept: the reply two exchanges back ends with a note of the start build
(`Aquí no se olvidó nada. Para que se olvide algo, pídelo en un mensaje aparte.` and its Romanian
form) that no build of tonight writes, so `model_text` keeps it and it names forgetting; HEAD read
only the last reply. One is now refused: `My alarm code is 5528.` after `Cancel the code I gave you.` and a reply asking
`Could you please clarify which code you are referring to, or let me know if there's something
specific you'd like me to ignore or stop using?`, which ran no call and names forgetting in words
`forget_open` does not read. That form is filed as
[R-1193](../refinements/tasks/1193-a-forget-in-words-no-reader-reads-is-refused-on-the-answer.md). Scripts `replay.py` and `diff.py`,
logs `head.json`, `new.json` and `diff_head_new.txt`, in
the `slot15` scratch directory of the 2026-11-13 run.

## The deed reader on the live stack: rows and the rule

Written 2026-11-13 at 08:07, before the draw. The build is `cortexn21-brain-s15deed` (port 23155,
the working tree with the deed reader, memory tools only), through the recording proxy.

- **Courtesy chains**, six draws: empty `memories`, send `Hi! How are you today?` in a new chat,
  then `My locker code at the pool is 7319.` in the same chat, every card approved. The reader holds
  when every forget call of the second turn is refused with `FORGET_UNREQUESTED` and every draw
  stores the locker row. It fails when such a call runs or a draw stores no locker row.
- **The cancel flow**, three draws: empty `memories`, store `Remember that my alarm code is 5528.`
  and `Remember that my locker code is 4242.` in two chats, send `Cancel the code I gave you.` in a
  new chat with every card denied, then `My alarm code is 5528.` in the same chat with every card
  approved. A draw decides when its first turn ran a forget call or its reply names forgetting and
  its second turn calls the tool. The reader holds when every such call runs and its card deletes
  the alarm row and keeps the locker row; it fails when such a call is refused. A first turn that
  did neither is counted apart as the form the replay names, with its second turn's result. With
  fewer than two deciding draws, three more.
- **A picture chain** is not drawn: the stack's cortex model reports no vision tower, so a turn
  with a picture is refused before anything is stored. The turn test
  `test_a_statement_after_a_picture_refuses_the_forget_as_without_it` covers it.

## The deed reader on the live stack: what was drawn

Drawn from 08:07 to 08:14 on 2026-11-13, proxy log lines 994 to 1103, SM clock 0.58 of
`clocks.max.sm` before and after.

| Flow | Draws | Deciding draws | Forget calls on the deciding turn | Rows after |
| --- | --- | --- | --- | --- |
| courtesy chain | 6 | 6 | 2, refused 2 of 2 | locker row stored 6 of 6 |
| cancel flow | 6 | 1 | 1, run 1 of 1 | alarm row deleted, locker row kept, 1 of 1 |

**Result: the reader holds**, on one deciding cancel flow. Five first turns ran a forget call (four
cards denied, one call that deleted nothing) and one asked `what you'd like me to ignore or cancel?`
with no call, the form of R-1193. After a run the second turn called the tool once, and the call
ran; in the other four the model only noted the statement and made no call. After the question
it asked again and made no call. Scripts `draw.sh`, `deciding.py` and `summ.py`, logs `draw.log`
and `draws.jsonl`, in the slot directory above.

## A reply the brain closed as a false claim, 2026-11-14

`claim_corrected` (`reply_notes.py`) reads whether `UNFORGOTTEN_CLAIM_NOTE` or `HANDED_CLAIM_NOTE`,
in any of their five languages, is among the notes the brain appended to an earlier reply.
`forget_open` then reads that reply's words as naming no forget, since the note already told the
person that nothing was forgotten. A forget run and a person's message that `asks_to_forget` reads
still open it.

`HANDED_CLAIM_NOTE` closes the cortex's reply on a turn its calls hand to the deep model. That turn
stores two assistant messages under one turn id: the cortex's reply with its notes
(`TurnEngine.handle_turn`), then the deep model's (`BrainPhase._persist`), and `_exchange`
(`tool_loop.py`) reads the last one. After a handoff the deep model answered, the note is
therefore not in the text read. The deep phase appends its reply only after its stream ends, so a
handoff whose stream is closed early stores none, and the cortex's reply closed by the note is
then the last of its turn. This is read from the code and was not drawn on a stack. Before
2026-11-15 the reader took only `UNFORGOTTEN_CLAIM_NOTE`, and such a reply's false claim of a
delete kept the forget tool on the next plain fact.

**Replay.** The three test files keep every earlier result (794 tests). The stored chats of
`cortexn22` (111 chats, 4 messages with an earlier exchange) and proxy lines 1 to 454 (3 distinct
requests with an earlier exchange) hold no reply closed by the claim note, so no result changes.
The recorded `a1` chain of [the notes](forget-unrequested-notes.md#the-draws-2026-11-13), whose
`Recuerda que mi color favorito es el verde.` had its forget call run, is now refused. Scripts
`replay.py` and `replay_sessions.py` are in
the `slot6` scratch directory of the 2026-11-14 run.

**Rule**, written at 01:28 before any draw. Brain `cortexn22-brain-s6claim` (port 23067, the
working tree), a new chat per draw, `memories` emptied first, every card approved. Chain A stores
`My alarm code is 5528.`, sends `Cancel the code I gave you.`, then `My alarm code is 5528.`;
chain B sends `Get my alarm code out of there.` and then `My locker code is 4242.`; chain A2 is A
with nothing stored. It passes when every message after a reply closed by the claim note runs no
forget call and every row it states is stored, and fails when such a call runs or a row is lost.
A message after any other reply is counted only. No claim note in the draws is a null result for
the fix, and the tests decide.

| Chain | Draws | Forget turn | Next turn | Rows at the end |
| --- | --- | --- | --- | --- |
| A, row stored | 3 | call ran and deleted the row, 3 of 3 | no forget call | code stored again, 3 of 3 |
| B, row stored | 3 | call ran and deleted the row, 3 of 3 | no forget call | locker row stored, 3 of 3 |
| A2, no row | 3 | no call: named forgetting 2, asked naming none 1 | no forget call | code stored, 3 of 3 |

**Result: null.** No reply of the 9 forget turns was closed by the claim note, so the fix was not
reached live. The reply that asked a question naming no forget, the form of
[task 1193](../refinements/tasks/1193-a-forget-in-words-no-reader-reads-is-refused-on-the-answer.md),
came 1 of 9 times, with nothing stored to delete, and the next turn made no forget call. Proxy
lines 457 to 534, SM clock 0.58 of `clocks.max.sm` after the draws; logs `drawA.log`,
`drawB.log` and `drawA2.log` in the slot directory above.

## A forget in other words, then a new value, 2026-11-27

The count of [task 1193](../refinements/tasks/1193-a-forget-in-words-no-reader-reads-is-refused-on-the-answer.md),
with its rule written in the task before the first draw. The brain was built from the tree, the
model host ran on compose defaults (the cortex `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, engine build
b12375, context 16,384, the default cache type, the MTP drafter at a draft length of 3, no
reasoning flag), and every card was approved. Each draw put the old row back and sent one chat of
two turns. Neither means no forget call ran and the reply's own text names no forgetting.

| first message, then | forget ran | it deleted | asks | names forgetting | neither | second turn: call | refused | old row kept | new value stored |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Cancel the code I gave you.`, then `My alarm code is 5528.` | 6 | 4 | 1 | 7 | 1 | 8 | 1 | 2 | 1 |
| `Get my phone number out of there.`, then `My phone number is 0721 555 9876.` | 8 | 0 | 2 | 8 | 0 | 4 | 0 | 4 | 4 |
| `Scrap the code.`, then `My alarm code is 5528.` | 0 | 0 | 8 | 8 | 0 | 1 | 0 | 8 | 7 |

Each row is 8 draws. The task's form (neither, then the statement's call refused with the old row
kept) came in 1 of 24, under the rule's bar of 2 on every message, and that reply ended with the
old value note: `(A remembered exchange still holds 4242, the value your message corrects, so a
later chat can still recall it. ...)`. The old row was kept in 14 of 24 draws, and the old value
note was shown in all 14.

Every first call on the phone message ran and deleted nothing: its result said the message was
not read as meaning a row holding that value, so the row was kept. `Scrap the code.` was answered
as a request about program code in 8 of 8, each reply asking which code; each named scrapping or
discarding, so the next turn kept the tool, and it wrote a call in 1.

The new value was not stored in 12 of 24, each after a forget call ran in the statement's own
turn. In 6 that call deleted the old row; in the other 6 its text was the new value or the whole
statement, it matched nothing, and the turn still stored nothing
([the rule that stores it](#a-statement-after-a-forget-stored-2026-11-27)).
Logs: `~/.cache/cortex-run/2026-11-27/s1/`, labels `b1` to `b3`.

## A statement after a forget, stored, 2026-11-27

The pass rule was written before the first draw. `memory_withheld` (`memory_claim.py`) records a
turn with `forget_memories` runs when its message, read alone, asks no question and is one
`forget_unrequested` refuses the tool on (`opened_earlier`, `forget_opened_earlier.py`), so only an earlier exchange opened the
forget, and either every call matched nothing, or every run succeeded, kept no row and was not
denied, the turn knows each deleted row's text, each such row holds a whole value, the message and
the reply hold none of those values, those rows name no word for a fact beyond the message's own,
and the reply says it noted the message. A call that matched nothing on such a message gets no
`FORGET_NOT_KEPT_NOTE`. Pass: the new value stored in every draw whose statement turn ran calls
that all matched nothing (0 of 6 on the draws above); no stored row holding a value a call of the
same draw deleted; no stored turn showing `(Nothing in this message was kept in memory. ...)`.

The draws above were repeated, 8 per message with the old row seeded, on a brain built from the
candidate and the same model host: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, engine build b12375,
context 16,384, the default cache type, the MTP drafter at a draft length of 3, no reasoning flag.
Each count is over the statement turn of the 8 draws.

| first message | matched nothing: stored | deleted the old row: stored | no call run: stored | new value stored | rows holding a deleted value | stored turns with the not kept note |
| --- | --- | --- | --- | --- | --- | --- |
| `Cancel the code I gave you.` | 2 of 2 | 0 of 0 | 6 of 6 | 8 | 0 | 0 |
| `Get my phone number out of there.` | 1 of 1 | 4 of 4 | 3 of 3 | 8 | 0 | 0 |
| `Scrap the code.` | 0 of 0 | 0 of 0 | 8 of 8 | 8 | 0 | 0 |

The rule passes. The new value was stored in 24 of 24 draws, against 12 of 24 before. The not kept
note showed on none of the 48 turns, and no result of a call that matched nothing included
`FORGET_NOT_KEPT_NOTE`. The old row was kept in 16 draws, each statement turn of them showing the
old value note. One stored reply said the code would not be stored; that turn ran no forget call,
and its reply ended with the note that the exchange is stored in memory. The first turn deleted
the old row in 4 `Cancel` draws, and none of those turns was recorded, since no reply said it noted
anything. The statement turn wrote a forget call in 3 of the 8 `Cancel` draws, against 8 of 8
above; the model reads nothing different before its first call of either turn, so that count
moved between the two draws on its own.

The drawn brain also required `asks_to_forget` to be false and compared the reply's words, not the
message's, with the deleted rows' words. None of the 9,445 strings in the core tests is read by
`asks_to_forget` or `asks_to_forget_keeping` while `forget_unrequested` refuses the tool on it, so
the committed check drops that condition. The stored reply includes the brain's notes, which the
note check does not see, so a check on the reply's words can differ between the two reads of one
turn. The committed check reads the rows' words against the message, and gives the same result on
every turn of the draws: the four deleted rows of the phone draws name only `phone`, which the
message holds, and the four first turns that deleted a row were withheld on their replies. A
forget of a value never stored, in an English statement `forget_unrequested` refuses the tool on
(`My PIN is 4821 too.`), is now recorded with that value. Logs:
`~/.cache/cortex-run/2026-11-27/c4b/`, labels `b1` to `b3`.

A question is not read. Over 1,744 turns generated from 52 forms typed after a forget, in English,
French, German, Spanish and Romanian, each naming a value, with a call that matched nothing or
deleted the row holding it, a check that also read questions stored 80 turns that the tree before
it withheld. Each was an English question that names the value it asks to forget (`Can you do the
same with my PIN 4821?`, `What about my PIN 4821?`, `And the PIN, 4821?`), with a call that
matched nothing. With the question condition the check stores none of the 1,744. Logs:
`~/.cache/cortex-run/2026-11-27/a1/` (`gen0.py`).

The forms were then drawn with the old row seeded, 8 draws each, on the model host as the stack
starts it: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, `--ctx-size 16384`, the MTP drafter at
`--spec-draft-n-max 3`, the default cache type, no reasoning flag, engine build b12375. The pass
rule, written before any row was read: the new value stored in every draw whose statement turn ran
calls that all matched nothing; no stored row holding a value a call of the draw deleted; no stored
row holding `4821`; no stored turn showing the not kept note. The last message was drawn on a
brain without the question condition and again on one with it.

| first message, then second | matched nothing: stored | deleted the old row: stored | other: stored | rows holding a deleted value | rows holding `4821` |
| --- | --- | --- | --- | --- | --- |
| `Cancel the code I gave you.`, `My alarm code is 5528.` | 3 of 3 | 2 of 2 | 3 of 3 | 0 | 0 |
| `Get my phone number out of there.`, `My phone number is 0721 555 9876.` | 1 of 1 | 3 of 3 | 4 of 4 | 0 | 0 |
| `Scrap the code.`, `My alarm code is 5528.` | 2 of 2 | 0 of 0 | 6 of 6 | 0 | 0 |
| `Forget my alarm code.`, `Can you do the same with my PIN 4821?`, no question condition | 8 of 8 | 0 of 0 | 0 of 0 | 0 | 8 |
| the same, with the question condition | 0 of 8 | 0 of 0 | 0 of 0 | 0 | 0 |

The new value was stored in all 24 draws of the first three messages, and the not kept note showed
on none of the 80 turns. Without the question condition the exchange naming `4821` was stored in
all 8 draws, each after a call for `4821` matched nothing and the reply said nothing was found, so
the rule failed there. With it none was stored and each such call's result ended with
`FORGET_NOT_KEPT_NOTE`. The first turn deleted the alarm row in all 16 draws of the last message.
Logs: `~/.cache/cortex-run/2026-11-27/a1/`, labels `b1` to `b4` and `f4`.
