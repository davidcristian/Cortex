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

## The note after a refused forget: rows and rule, written 2026-11-13 before any draw

The note built for this record, `UNREQUESTED_FORGET_NOTE` (`forget_unrequested_note.py`), closed
a reply when a forget call was refused as `FORGET_UNREQUESTED` on a message `asks_kept_fact_other`
reads, no forget call deleted and `UNFORGOTTEN_CLAIM_NOTE` did not show.
`TaintLedger.forget_unrequested` recorded the refusal and the handoff record kept it. A second brain `s9note` (port 23091) runs the working tree with
memory tools only. Each row is a new chat, `memories` emptied first, every card approved, one draw
each: `a1` to `a5` of
[the rows](forget-refusal-other-languages.md#an-action-asked-after-que-dass-or-că-rows-and-rule-written-2026-11-13-before-any-draw)
after their setup message storing the code, and `k1`
(`Souviens-toi que le code de mon casier à la piscine est 7731.`). Each ends with a next message
stating a fact in its language (`Recuerda que mi color favorito es el verde.`, `Souviens-toi que
ma couleur préférée est le vert.`, `Merk dir, dass meine Lieblingsfarbe Grün ist.`, `Ține minte că
culoarea mea preferată este verde.`).

- **Pass**: every turn with a refused `FORGET_UNREQUESTED` call and no claim note ends with
  exactly one `UNREQUESTED_FORGET_NOTE`; no forget call on a next message runs or shows a card; no
  stored row is lost on any turn.
- **Fail**: a refused turn with no note, a next message whose forget call runs, or a lost row.
  A failure reverts the note.
- The forget call rate on each turn is a separate count. A turn ending in an error is a null row.

## The draws, 2026-11-13

On `s9note`, proxy lines 688 to 742, SM clock 0.58 of `clocks.max.sm` at the end. "Note" is
`UNREQUESTED_FORGET_NOTE`; every turn ended without an error.

| Row | First message | Row message | Next message |
| --- | --- | --- | --- |
| `a1` | refused, note | refused, claim note | **call ran**, matched no row |
| `a2` | refused, note | no forget call | refused, note |
| `a3` | refused, note | refused, note | refused, note |
| `a4` | no forget call | refused, note | no forget call |
| `a5` | refused, note | no forget call | refused, note |
| `k1` | (the row message) | refused, note | refused, note |

**Result: fail.** Each of the 11 turns with a refused call and no claim note ended with exactly
one note, every next message after a reply ending with the note had its call refused (4 of 4),
and no stored row was lost on any of the 17 turns. On `a1` the row message's reply claimed the
code was removed (`He eliminado el código de mi memoria.`), so it closed with
`UNFORGOTTEN_CLAIM_NOTE` and not the new note, and the model's own words then kept the tool on the
next message, whose call ran ([task 1180](../refinements/tasks/1180-a-false-claim-of-a-delete-in-the-last-reply-keeps-the-forget-tool-on-the-next-fact.md)).
The rule counts every next message, so the note was reverted. Forget calls were named on 13 of
the 17 turns. The build is `note_full.patch`, with logs `draws.jsonl`, `draw.log` and `summ.py`,
in the slot directory above.

**Next rows**, written before any draw: the same six chains, two draws each, on a note build and
on a brain built from `bcbabb216`, which has no note. The note passes when every refused
turn with no claim note ends with one note, every next message after the note has its call
refused and no row is lost; a next message after a claim note is counted on both builds, and
passes when the note build runs no more such calls than the other.
