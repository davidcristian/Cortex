# Readings: the rise of forget calls on a request to remember

On 2026-11-12 the cortex called `forget_memories` on 7 of the 8 first requests of the language
setup ([recalled memory language](recalled-memory-reply-language.md)) and on 94 of 135 first
requests of the store turns in the `cortexn20` proxy log
([task 1163](../refinements/tasks/1163-a-refused-forget-call-on-a-request-to-remember-costs-a-round.md)).
On 2026-11-07 the French, German and Romanian requests made no forget call in 9 draws
([language flows](overlay-language-and-locale-flows.md#8-requests-to-remember-in-four-more-languages)),
and on 2026-10-31 the cortex called it on 4 and 5 of 15 requests over an empty pool
([listed tools](unasked-tools-listed-on-remember.md)). This record separates the causes.

## What the log shows before any draw

The eight first requests of the setup held no recall block: the cortex saw the system message,
the person's message and five tools, `list_scheduled`, `cancel_scheduled`, `snooze_scheduled`,
`edit_scheduled` and `forget_memories`. The `cortexn20` stack runs with `CORTEX_TOOLS_BACKEND`
unset (no sidecar tools), no subagents and no body, so it lists no `spawn_subagents`, no
`escalate_to_brain`, no file tools and no body tool. The 2026-11-07 stack listed
`spawn_subagents`, since one of its draws called it. That night's full tool list is not in the
tree; the two brain tools are the part of it this record can rebuild.

## Rows and rule, written 2026-11-12 before any draw

| Row | Message | Language |
| --- | --- | --- |
| `m1` | `Remember that my bike lock code is 5180.` | English |
| `m2` | `Remember that my dentist is called Dr Weber.` | English |
| `m3` | `Merk dir, dass mein Hund Bello heißt.` | German |
| `m4` | `Souviens-toi que le code de mon casier à la piscine est 7731.` | French |

Conditions, each a first request of a new chat:

- **H**: the brain code of `master` at this record (second brain `s10cand`), empty pool.
- **S**: the start build `d1620de90` (second brain `s1head`), empty pool. One turn per row on H
  and on S gives the two first requests. When they are the same text, the build cannot reach the
  first request, explanation (a) is out, and S is not drawn again.
- **P**: H with the eight rows the language setup stored, whose `m3` and `m4` rows hold the
  brain's note that nothing was deleted. Drawn only for a row whose first request holds a recall
  block with that row; a row with no block is reported, since the pool cannot reach it.
- **T**: H's recorded first request with `escalate_to_brain` and `spawn_subagents` added after
  the five tools, their specs built from the brain code.

H, P and T are drawn by sending the recorded first request to the model host through the
recording proxy five times per row, with nothing else changed, and counting the responses that
call `forget_memories`. No brain runs these draws, so no row is stored.

What each outcome means:

- **(a) tonight's code**: H and S first requests differ and H calls more often than S by at
  least 3 of 20 draws.
- **(b) the pool**: P calls on at least 3 more of its draws than H on the same rows. When the
  setup requests held no recall block, the pool cannot explain the setup's 7 of 8 whatever P shows.
- **(c) the stack, not the code**: T calls on at least 8 fewer of its 20 draws than H. That names
  the shorter tool list of this stack, which earlier nights' code did not change, as the cause.
- **(d) draw noise**: H calls on at most 4 of 20, near the 2026-10-31 rate, so tonight's counts
  were a run of draws and not a change.
- H calling often with none of (a), (b) and (c) holding leaves earlier nights' code, or a stack
  difference T does not rebuild, as untested causes; a build of the 2026-11-07 tree decides it.

## Condition L, written 2026-11-12 after H, S, P and T and before L was drawn

The model host's image is built `FROM ghcr.io/ggml-org/llama.cpp:server-cuda`, a tag that moves,
and tonight's build runs llama-server build 12282 (`aa75ff323`), where 2026-11-07 ran 12169 and
2026-10-31 ran 12004. **L** sends H's four recorded first requests five times each to a second
llama-server from `ghcr.io/ggml-org/llama.cpp:server-cuda-b12169`, with the same model file and
flags (`-ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram 8192`). L calling on at least
8 fewer of its 20 draws than H names the llama-server build as the cause; L within 3 of H rules it
out.

**C**, written after L was drawn and before C was: the brain code of 2026-11-07 (`59c23be0f`)
builds the same system message and the same specs for four of the five tools; only
`edit_scheduled` differs, by the `at` argument added since. C sends H's requests with that tool's
2026-11-07 spec in its place, five times per row, on the stack's llama-server. C calling on at
least 8 fewer of 20 than H names the code of the nights between as the cause.

Draws stop at 20 minutes; a condition not drawn by then is named as not drawn.

## The draws, 2026-11-12

The `cortexn20` stack: gemma-4-12B (`gemma-4-12b-it-qat-q4_0.gguf`) at a context of 16,384
tokens, llama-server build 12282, every card approved. SM clock at the draws: 0.57 to 0.73 of
`clocks.max.sm`.

| Condition | `m1` | `m2` | `m3` | `m4` | All |
| --- | --- | --- | --- | --- | --- |
| H, through each brain once | 1 of 1 | 1 of 1 | 1 of 1 | 1 of 1 | 4 of 4 |
| S, through each brain once | 1 of 1 | 1 of 1 | 1 of 1 | 1 of 1 | 4 of 4 |
| H, recorded request | 4 of 5 | 2 of 5 | 4 of 5 | 4 of 5 | **14 of 20** |
| T, two brain tools added | 5 of 5 | 2 of 5 | 3 of 5 | 3 of 5 | **13 of 20** |
| L, llama-server build 12169 | 5 of 5 | 4 of 5 | 5 of 5 | 3 of 5 | **17 of 20** |
| C, the 2026-11-07 `edit_scheduled` | 4 of 5 | 5 of 5 | 5 of 5 | 4 of 5 | **18 of 20** |
| P, the setup pool recalled | | | 1 of 5 | 1 of 5 | **2 of 10** |

The H and S first requests were the same text on all four rows, so (a) is out without a draw.
Each P request held a recall block with the row's stored fact and its note; on the same two rows
H called on 8 of 10. The P turn of `m4` through the brain showed a card listing the stored French
row (`Listed because they also hold 7731`), and the approved card deleted it. T's draws called
`spawn_subagents` three times, with an instruction to remember the fact.

**Result.** None of (a), (b), (c) and (d) holds. Tonight's code does not reach the first request;
the pool lowers the calls rather than raising them, and the setup's requests held no recall block;
the two brain tools, the code since 2026-11-07 and the llama-server build each leave the rate
within 4 of H; and 14 of 20 is far above the 4 of 15 and 5 of 15 of 2026-10-31. What tonight's
requests share is an empty recall block and a list of five tools with no body and no sidecar tool,
a condition no earlier record drew: the 2026-11-07 draws came after flows of that night had stored
the same facts, and the 2026-10-31 draws listed the body's tools. Those two stack differences are
not separated here
([task 1165](../refinements/tasks/1165-the-forget-calls-on-a-request-to-remember-are-not-measured-beside-the-body-tools.md)).
A brain-appended note in a stored row does not raise the calls on these rows, so the note stays in
the row, as the turn stores what it showed.

**Method.** `first.sh` (the brain turns), `replay.py <proxy.jsonl> <condition> <draws> <line>...`
(the direct draws; `URL` names another server, `EDIT` the spec for C), `cmp.py` (the H and S
requests) and `srccheck.py` (the request text against a source tree), in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot11/`.

## The refusal in four more languages

`forget_unrequested` now reads French, German, Spanish and Romanian by its word lists, which name
the forget verbs, the words of a correction and the negations of those languages. Its letter
clause keeps the forget tool only on a letter outside those four languages and English, so a
message in Polish, Russian, Korean or Japanese still keeps it. The lists also gained `retir`,
`enlev`, `quit`, `scoat`, `streich`, the past forms `gelöscht` and `șters`, the corrections
(`plus`, `au lieu`, `mis à jour`, `statt`, `geändert`, `en lugar`, `cambió`, `în loc`, `schimbat`)
and "from your memory" (`de ta mémoire`, `aus deinem Gedächtnis`, `de tu memoria`, `din memorie`),
the form the English `out of memory` has. A bare word for memory is left out, since `garde en
mémoire` asks to keep. The forget verbs of Portuguese, Catalan, Italian and Turkish (`esqueça`,
`oblida`, `scorda`, `sil`) are listed too, since those languages are written in the same letters.
Their words of a correction are not, so a Portuguese correction such as
`Meu código mudou para 4862.` has the tool refused
([task 1166](../refinements/tasks/1166-a-correction-in-portuguese-refuses-the-forget-tool.md)).

### Rows and rule, written 2026-11-12 before any draw

A second brain `s12lang` (port 23072) runs the working tree with this reader. Every draw starts
from slot 10's eight setup rows, restored before each turn, so each fact has a stored row the
recall block can show, the condition P above drew. Each turn is a new chat, every card approved.

| Row | Message | Draws |
| --- | --- | --- |
| `k1` | `Souviens-toi que le code de mon casier à la piscine est 7731.` | 3 |
| `k2` | `Merk dir, dass mein Hund Bello heißt.` | 3 |
| `k3` | `Recuerda que mi color favorito es el verde.` | 3 |
| `k4` | `Ține minte că numărul apartamentului meu este 42.` | 3 |
| `x1` | `Oublie le code de mon casier à la piscine.` | 2 |
| `x2` | `Vergiss, wie mein Hund heißt.` | 2 |
| `x3` | `Olvida mi color favorito.` | 2 |
| `x4` | `Uită numărul apartamentului meu.` | 2 |

The change leaves the first request as it was (the tool stays listed and a call to it is refused),
so the rule is about what the reader does to a call, and the call rate is a separate count.

- **Pass on `k1` to `k4`**: no draw shows a card, no draw deletes the stored row of its fact, and
  every `forget_memories` call on these turns is refused with the reader's `asks to forget nothing`.
- **Pass on `x1` to `x4`**: no forget call is refused by `forget_unrequested`. Whether the card
  appears and deletes the row is counted beside it, since the card and the match are other code.
- **Fail**: a remember draw runs a forget call or loses its row, or a forget draw has its call
  refused. A failure reverts the reader change.

### The replay and the draws, 2026-11-12

Replayed through the old and new reader, 8 of the 191 recorded turns (177 distinct messages) in
the `cortexn20` proxy log changed, all to refused: the four requests to remember of the language
setup and the four questions in French, German, Spanish and Romanian. Of 28,755 distinct strings
in the brain's test files and the backticked text of `docs/`, 656 changed. 608 are now refused:
requests to remember, reminders, questions, replies and fragments in the four languages, with no
request to forget or correction among them once the replay had found `gelöscht`, `șters`,
`ștearsă`, `modifié` and `mis à jour`, which the lists now name. 48 now keep the tool: the new
verbs and corrections, and 22 English strings holding `plus`. `unasked_tools` and
`unasked_forget`, which share `RETRACT_WORDS`, changed on none.

On `s12lang`, SM clock 0.57 of `clocks.max.sm`, proxy lines 1060 to 1143:

| Rows | Draws | Forget calls | Refused by the reader | Cards | Fact row after |
| --- | --- | --- | --- | --- | --- |
| `k1` to `k4`, remember | 12 | 4 (`k1` 1, `k2` 1, `k4` 2) | 4 of 4 | 0 | kept on 12 of 12 |
| `x1` to `x4`, forget | 8 | 8 | 0 of 8 | 8, approved | deleted on 8 of 8 |

**Result: pass.** Every forget call on a request to remember was refused and no stored fact was
lost, where condition P above lost the French row to an approved card on the old reader. Every
forget request reached the tool, and each card deleted the fact's row. Each reply was in the
person's language and said the fact was kept or forgotten. The image was built before `error`
left the list, a word none of the 20 messages holds. Scripts: `draw.sh`, `summ.py`,
`collect.py`, `replay.py`, `replay_ua.py` and `diff.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot12/`.
