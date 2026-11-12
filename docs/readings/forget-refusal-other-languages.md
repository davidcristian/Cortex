# Readings: the forget refusal on a request to remember in four more languages

`forget_unrequested` now reads French, German, Spanish and Romanian by its word lists, which name
the forget verbs, the words of a correction and the negations of those languages. On a message
that `asks_kept_other` reads as a request to remember in one of those four languages (`souviens-toi`,
`merk dir`, `recuerda que`, `ține minte`), its letter clause keeps the forget tool only on a letter
outside them and English. On any other message a letter outside `a-z` keeps the tool, so a request
to forget in Italian, Portuguese, Catalan, Dutch or Polish keeps it by its accented letters, and
so does a question in the four languages. The lists also gained `retir`,
`enlev`, `quit`, `scoat`, `streich`, the past forms `gelöscht` and `șters`, the corrections
(`plus`, `au lieu`, `mis à jour`, `statt`, `geändert`, `en lugar`, `cambió`, `în loc`, `schimbat`)
and "from your memory" (`de ta mémoire`, `aus deinem Gedächtnis`, `de tu memoria`, `din memorie`),
the form the English `out of memory` has. A bare word for memory is left out, since `garde en
mémoire` asks to keep. The forget verbs of Portuguese, Catalan, Italian and Turkish (`esqueça`,
`oblida`, `scorda`, `sil`) are listed too, since those languages are written in the same letters.
Their other words for removing and their words of a correction are not. A reader that read the
four languages' letters on every message refused the tool on requests to forget such as
`Butta via la nota sulla palestra, è vecchia.` and `Wis wat ik zei over België.`, and on
corrections such as `Meu código mudou para 4862.`: of 37 such messages in Italian, Portuguese,
Catalan and Dutch, the reader before it kept the tool on 36 and it kept the tool on 8.

## Rows and rule, written 2026-11-12 before any draw

A second brain `s12lang` (port 23072) runs the working tree with this reader. Every draw starts
from slot 10's eight setup rows, restored before each turn, so each fact has a stored row the
recall block can show, the condition P of the
[separation](forget-calls-on-remember-rise.md#rows-and-rule-written-2026-11-12-before-any-draw) drew. Each turn is a new chat, every card approved.

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

## The replay and the draws, 2026-11-12

Replayed through the reader that read the four languages' letters on every message and the one
before it, 8 of the 191 recorded turns (177 distinct messages) in
the `cortexn20` proxy log changed, all to refused: the four requests to remember of the language
setup and the four questions in French, German, Spanish and Romanian. Of 28,755 distinct strings
in the brain's test files and the backticked text of `docs/`, 656 changed. 608 are now refused:
requests to remember, reminders, questions, replies and fragments in the four languages, with no
request to forget or correction among them once the replay had found `gelöscht`, `șters`,
`ștearsă`, `modifié` and `mis à jour`, which the lists now name. 48 now keep the tool: the new
verbs and corrections, and 22 English strings holding `plus`. `unasked_tools` and
`unasked_forget`, which share `RETRACT_WORDS`, changed on none.

The reader as built reads those letters only on a request to remember. Replayed through it, the
reader that read them on every message and the start build `d1620de90`, over 203 recorded turns (189 distinct messages, proxy
lines 1 to 1143) and 28,863 test and docs strings, it refuses on 3 turns and 83 strings that the
start build kept. Each is a request to remember in French, German, Spanish or Romanian or a part
of one (the turns are `k1`, `k2` and `k4`; `k3` has no letter outside `a-z`). It keeps the tool on 5
turns and 569 strings the every-message reader refused, among them five questions in the four
languages, and refuses on none it kept. On the 37 messages above and six in Swedish,
Finnish, Norwegian and Polish it gives the start build's result: 42 keep the tool, and
`Descarta el que et vaig dir de la meva salut.` is refused by all three, since every letter is in
`a-z` ([task 1168](../refinements/tasks/1168-a-request-to-forget-in-another-language-written-in-a-z-refuses-the-forget-tool.md)).
On the 20 draw messages above it gives the result `s12lang` gave, so the draws hold for it.
Scripts: `diff3.py` and `drawdiff.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot14/`.

The Romanian verbs `uita` and `scoate` take `ț` in the second person (`să uiți`, `să scoți`),
which the lists' `uit` and `scoa[st]` did not read, so `Amintește-ți să uiți codul meu de la sală.`
and `Ține minte să scoți codul meu din listă.` had the tool refused. The lists now read `ui[tț]`
and `scoți`, also as `scoti` without diacritics, in the message and in the reply and message
before it. Replayed over the same 203 turns and 28,863 strings, the `ț` forms alter no result of
`forget_unrequested`, `unasked_tools` or `unasked_forget`. Over the 203 turns and 28,901 strings,
`scoti` and the reading of the earlier texts change no result on a message. Read as the reply and
the message before one, 7 strings now keep the tool, each naming `uiți` or `scoți`, two of
them a habit or a reminder (`Ține minte că mereu uiți cheile.`), as `forget` in English does.

A request to remember that names removal by a word outside the lists still had the tool refused
(`Ține minte să arunci codul.`, `Merk dir, den Code wegzuwerfen.`, `Souviens-toi : jette mon
code.`). The four languages' letters are now read only on a request that `asks_kept_fact_other`
reads as one stated fact: the request opens the message after any thanks, `que`, `dass` or `că`
follows the remember verb, and no second clause or sentence follows the fact. Any other request
to remember in those languages keeps the tool, since a colon, `să`, `de` or `zu` with a verb, or
a second clause can ask for an action, and no list can name every verb for one. None of the 81
recorded messages that `asks_kept_other` reads had such a form: each was `k1` to `k4` or a
recall prompt quoting one. Replayed through the start build, the reader before this change and
this one over 203 turns and 28,901 strings, no turn changed from the reader before, and 122
strings now keep the tool and none is newly refused. Those 122 are requests to remember an
object, a fact after a colon or a comma with no `dass`, a fact beside a second clause or
sentence, a remember verb after the fact, and stored row texts opening with `User:`. Of the 22
strings refused that the start build kept, 21 state one fact or are part of such a request, and `Recuerda que remuevas mi
código.` asks for an action with `que` and a subjunctive ([task 1171](../refinements/tasks/1171-a-request-to-remember-an-action-stated-after-que-dass-or-ca-refuses-the-forget-tool.md)). Scripts: `kept_other.py` and
`headdiff.py` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot17/`,
with `diff3.py` of slot 14.

A fact clause that asks the assistant for an action with a verb in no list still had the tool
refused (`Recuerda que debes tirar mi código.`, `Merk dir, dass du meinen Code wegwerfen
sollst.`). `asks_kept_fact_other` now reads no stated fact when the clause holds an obligation of
the assistant or a second `que tu`, marked by closed words only: `tu dois`, `vous devez`, `il
faut`, `debes`, `tienes que`, `hay que`, `trebuie`, `să`, `sollst` and `musst`. `Ține minte că
trebuie să plec la 9.` states a fact about the person and keeps the tool too, while `Merk dir,
dass ich morgen arbeiten muss.` and `Souviens-toi que je dois partir à 9 h.` are still refused.
Replayed through the start build, HEAD before this change and this one over 203 turns and 28,952
strings, no turn changed from HEAD, 13 strings now keep the tool and none is newly refused. Each
of the 13 asks the assistant for an action, except the `trebuie să plec` fact. Of the 26 strings
and 3 turns (`k1`, `k2`, `k4`) refused that the start build kept, each states one fact or is a
fragment of such a request (`reține că`), except `Recuerda que remuevas mi código.`, whose second
person subjunctive no closed word marks. Scripts: `replay.py` of slot 12, `diff3.py` of slot 14
and `headdiff.py` of slot 17, with the logs in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot20/`.

On `s12lang`, SM clock 0.57 of `clocks.max.sm`, proxy lines 1060 to 1143:

| Rows | Draws | Forget calls | Refused by the reader | Cards | Fact row after |
| --- | --- | --- | --- | --- | --- |
| `k1` to `k4`, remember | 12 | 4 (`k1` 1, `k2` 1, `k4` 2) | 4 of 4 | 0 | kept on 12 of 12 |
| `x1` to `x4`, forget | 8 | 8 | 0 of 8 | 8, approved | deleted on 8 of 8 |

**Result: pass.** Every forget call on a request to remember was refused and no stored fact was
lost, where condition P of the separation lost the French row to an approved card on the old reader. Every
forget request reached the tool, and each card deleted the fact's row. Each reply was in the
person's language and said the fact was kept or forgotten. The image was built before `error`
left the list, a word none of the 20 messages holds. Scripts: `draw.sh`, `summ.py`,
`collect.py`, `replay.py`, `replay_ua.py` and `diff.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot12/`.
