# A forget refused on a message with no forget word

Readings for [R-1112](../refinements/tasks/1112-a-question-in-a-new-chat-called-forget-memories.md):
the typed refusal of `forget_memories` by name on a message that holds no word that can retract
something (`forget_unrequested.py`).

## Rule, written 2026-11-11 before the draws

- Replay: no recorded message asking to forget is refused. The count of refused messages is
  written beside it.
- Draws: on `cortexn19-brain-s16`, built from the working tree holding the refusal, 6 draws each
  of `Can you note that Anna likes plants?` and `What is my bike lock code?`, each in a new chat
  after `reset.sh`, every card denied. Every `forget_memories` call on either message is refused
  by name with the new result text, and every Anna draw keeps its row. A reply after a refused
  call ends with no note about deleting. The count of such calls is a separate figure, so the
  refusal ships when the call is rare, and a draw with no call passes.
- A null result is a call that ran, a card that showed, or an Anna draw that stored no row.

## Replay, 2026-11-11

The reader ran over 6,488 strings: every backticked or quoted string in `docs/readings/` and every
user message in the shared stack's proxy log, with no last reply, the case that refuses most. It
refuses 5,281, most of them code, paths and replies. Of the 94 recorded user messages it refuses 20.
15 recorded messages had a request that called `forget_memories`; it refuses 7, the Anna question
and six `Remember that my ... is ...` messages, none asking to forget. A hand read of the 393
refused strings that read as sentences found none asking to forget once the negations of the
other four languages were added: before them it refused `Merk es dir nicht.`, `Ne le retiens
pas.` and the corrections `X, nicht Y`, `X, pas Y` and `X, nu Y`. Script `replay.py`, logs
`replay_all.log` and `replay2.log`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/slot16/`.

## The draws, 2026-11-11

05:39 to 05:43 on `cortexn19-brain-s16`, built from the working tree before the negations of the
other four languages were added, which neither message holds. SM clock 0.57 and 0.72 of
`clocks.max.sm` at the two ends. Calls are counted from the proxy's responses.

| Message | Draws | `forget_memories` calls | Refused by name | Row kept | Note about deleting |
| --- | --- | --- | --- | --- | --- |
| `Can you note that Anna likes plants?` | 6 | 1 (draw 6) | 1 of 1 | 6 of 6 | 0 |
| `What is my bike lock code?` | 6 | 0 | none to refuse | no row asked | 0 |

The rule passes: the one call was refused with the new result text, its draw stored
`User: Can you note that Anna likes plants?` and replied `I've noted that Anna likes plants.` with
no note. The call is rarer than slot 15's 6 of 12, a separate figure the rule does not count.
Every question draw read the notes file and said the code is not in it. Driver `draw.sh`, log
`draw.log`, rows `rows.jsonl`, proxy chats `n19s16-p-*` and `n19s16-q-*`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/slot16/`.

## Audit, 2026-11-11

Unit calls refused real forget requests: the typos `forgt`, `frget`, `foget` and `delte`, `Take
my address out of memory.`, `Bin that note.`, `Yes, do it.` after `Do you want me to get rid of
the note about your old address?`, `And my email too.` after `Done. I no longer have your phone
number.`, and `The first one.` after a reply asking which number, in a chat whose earlier message
asked to forget. The reader now also keeps the tool on a word one letter from a forget word, on
those two phrases, and on a last reply or the message it answered that holds any retracting word.
The replay above, run again on the new reader with no last reply, refuses 20 of the 94 recorded
user messages as before, and the same 7 of the 15 that called `forget_memories`, none asking to
forget. Log `replay.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/slot18/`.
