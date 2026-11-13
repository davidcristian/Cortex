# Readings: the brain's notes in the last reply that the forget refusal reads

`forget_unrequested` keeps the forget tool when the chat's last reply names forgetting. The brain
appends its notes to that reply, and 14 of them name forgetting in all five note languages
(`Ask again to forget it`, `Aquí no se olvidó nada`), so after one of them the next request to
remember or question kept the tool, and an unasked call there reached the card. A draw of a new
note of that kind showed it: after the note on a refused setup turn, each next message had its
forget call run and its approved card delete the code row
([the draw](forget-refusal-other-languages.md#an-action-asked-after-que-dass-or-că-rows-and-rule-written-2026-11-13-before-any-draw)).

The tool loop now reads the last reply through `model_text` (`reply_notes.py`), which removes each
note the brain appended at the reply's end, matched by the note's own text in every language as
`place_note` sets it: a format field matches one line of any text, and a note that does not close
its bracket matches its `- ` item lines and the closing bracket. A note text the model wrote
inside its reply, or followed by text of its own, stays. `REPLY_NOTES` lists every note, and a
test fails when a module names a note constant the list does not hold, other than the notes
written into a tool result, a prompt or a summary.

## The replay, 2026-11-13

Replayed through HEAD `83ab2a7e8` and this tree, every recorded turn of the `cortexn21` proxy log
(lines 1 to 686, 147 distinct pairs of a message and its last reply) gives the same result. The
three turns after the note drawn above (lines 235, 242 and 248) end with that note's text, which
this tree does not append, so they are read as before.

The test and docs strings have no last reply of their own, so each of the 33,177 distinct strings
(18,521 in the brain's tests, 16,470 backticked in `docs/`, 131 proxy messages and 74 written for
the earlier replays) was paired with `Noted.` and each of the 179 note forms as the brain appends
it. 873 strings are refused with no last reply. After the 70 forms of the 14 notes that name
forgetting (`UNFORGOTTEN_CLAIM_NOTE`, `HANDED_CLAIM_NOTE`, `UNCALLED_FORGET_NOTE`,
`HANDED_FORGET_NOTE`, `UNMATCHED_FORGET_NOTE`, `HANDED_UNMATCHED_NOTE`, `DECLINED_FORGET_NOTE`,
`DELETED_UNFOUND_NOTE`, `FORGOT_COUNT_NOTE`, `INSIDE_NOTE`, `OLD_VALUE_NOTE`,
`NUMBERS_LEFT_NOTE`, `KEPT_BEYOND_CHAT_NOTE`, `CANCELLED_NOTE`), HEAD keeps the tool on all 873
and this tree refuses it, 61,110 pairs in all. After the other 109 forms no result changes, and no
string is kept by this tree that HEAD refused. `unasked_forget` reads the full last reply as
before, since it keeps the tool only on a question and no note asks one. Scripts `replay.py` and
`replay.json` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot9/`.
