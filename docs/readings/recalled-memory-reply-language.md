# Readings: the language of a reply built on a recalled memory

Whether the cortex answers in the language of the person's message when the memory it recalls was
written in another language. The recall block is `MEMORY_HEADER` in
`brain/packages/core/src/cortex_core/turn_context.py`; memory is
[ADR-0008](../adr/ADR-0008-memory-v1.md). The defect was first seen on 2026-11-07, when three of
four English questions about a fact stored in French, German, Spanish or Romanian were answered in
the fact's language ([flows](overlay-language-and-locale-flows.md)).

## Rows and pass rule, written 2026-11-12 before any draw

Eight facts are stored once, each in its own chat, through the base build. Both builds then ask
about the same eight rows: after every question the rows that question's own exchange wrote are
deleted, so each question recalls from the same eight stored rows.

| Row | Fact stored | Question, new chat | Message language |
| --- | --- | --- | --- |
| `f1` | `Souviens-toi que le code de mon casier à la piscine est 7731.` | `What is my swimming pool locker code?` | English |
| `f2` | `Merk dir, dass mein Hund Bello heißt.` | `What is my dog called?` | English |
| `f3` | `Recuerda que mi color favorito es el verde.` | `What is my favourite colour?` | English |
| `f4` | `Ține minte că numărul apartamentului meu este 42.` | `What is my apartment number?` | English |
| `e1` | `Remember that my sister is called Clara.` | `Comment s'appelle ma sœur ?` | French |
| `e2` | `Remember that my car is a blue Skoda.` | `Was für ein Auto habe ich?` | German |
| `e3` | `Remember that my favourite band is Radiohead.` | `¿Cuál es mi grupo de música favorito?` | Spanish |
| `e4` | `Remember that my neighbour is called Mihai.` | `Cum se numește vecinul meu?` | Romanian |

Each row is drawn three times per build, 24 questions per build. Builds:

- **base**: the brain code of the tree this record is committed on, without the sentence below.
- **candidate**: the same code with one sentence added to `MEMORY_HEADER`, saying a memory may be
  written in another language and the reply is in the language of the person's message.

**Pass rule.** A draw passes when its reply is in the language of the person's message. The
language check is a script (method below): a reply is in a language when most of the words that
belong to exactly one of the five languages' word lists belong to that one. A reply the script
calls mixed or unknown fails. Every reply is also read by eye and quoted where the two disagree.

**Reach.** Before counting, the first model request of each question on both builds is compared.
A row is counted only when both builds' first requests hold the recall block with that row's
stored fact, and differ only in the header sentence and the age text. A row the change cannot
reach is reported and left out of the counts.

**Stop rule.** If the base passes 22 or more of its 24 draws, the defect is not reproduced at this
tree: the record says so and the candidate is not drawn.

**Ship rule.** The candidate ships when, over the counted rows, all three hold:

1. it passes at least 6 more draws than the base;
2. it passes at least 7 in 8 of its counted draws (21 of 24 when every row counts);
3. no row the base passed in all three draws fails more than one draw on the candidate.

Otherwise the header is left as it is and the result is written here. A candidate within two
draws of the base is a null result: the sentence does not move the reply language.

## The draws, 2026-11-12

The `cortexn20` stack: the resident cortex (gemma-4-12B) at a context of 16,384 tokens, memory on
pgvector with the default `global` scope, each build a second brain on the stack network whose
model requests went through a recording proxy, every card approved, every question in a new chat.
SM clock at the draws: 0.57 of `clocks.max.sm`.

**Reach.** On all 24 question pairs the first model request with tools held the recall block with
the row's fact on both builds, and the two requests were the same once the candidate sentence and
the age texts were removed. Every row counts.

| Row | Base passes | Base replies in another language | Candidate passes |
| --- | --- | --- | --- |
| `f1` | 3 of 3 | none | 3 of 3 |
| `f2` | 1 of 3 | `Dein Hund heißt Bello.` twice | 3 of 3 |
| `f3` | 2 of 3 | `Tu color favorito es el verde.` | 3 of 3 |
| `f4` | 0 of 3 | `Numărul apartamentului tău este 42.` twice, `Apartamentul dumneavoastră are numărul 42.` | 3 of 3 |
| `e1` to `e4` | 12 of 12 | none | 12 of 12 |
| **All** | **18 of 24** | | **24 of 24** |

The script and the eye agreed on 47 of the 48 replies. The script called
`Apartamentul dumneavoastră are numărul 42.` mixed, since its word lists hold `are` only as
English; it is Romanian, a fail either way. Every English fact asked in another language was
answered in that language on both builds, so on these rows the defect showed in one direction:
a fact stored in another language pulled an English question's reply into that language.

**Result.** The candidate passes 6 more draws than the base, 24 of 24, and no row fails a draw it
passed on the base, so all three items of the ship rule hold and the sentence ships in
`MEMORY_HEADER`. The base reproduced the defect of 2026-11-07: 6 of the 12 English questions were
answered in the fact's language.

**Method.** `setup.sh` stores the eight facts, `ask.sh` (with `PORT`, `BUILD` and `DRAWS`) asks
the questions and deletes each question's own rows, `compare.py` compares the first requests and
counts the pass rule through `lang.py`, the language check, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot10/`.
`lang.py` keeps about 40 common words per language; a word in exactly one list votes for it, and
the reply's language is the one holding more than half of the votes.

Three of the four requests to remember in another language, French, German and Romanian, ran a
`forget_memories` call that matched nothing during the setup, and their stored rows hold the
note saying nothing was deleted
([forget calls on a request to remember](forget-calls-on-remember-rise.md)).

## A request for an answer in another language, rows written 2026-11-12 before the draws

The sentence tells the cortex to reply in the language of the person's message, which could
override a message that asks for another language. Three rows over the same eight stored rows,
two draws per build. A draw passes when the reply holds the asked language: German for `n1`, the
French for the number for `n2` and English for `n3`. A candidate draw failing where the base
passes is a defect of the sentence, filed as a task; both builds passing means the sentence
leaves such a request alone.

| Row | Question, new chat | Language asked for |
| --- | --- | --- |
| `n1` | `Tell me in German what my dog is called.` | German |
| `n2` | `How do I say my apartment number in French?` | French |
| `n3` | `Réponds en anglais : comment s'appelle ma sœur ?` | English |

**Drawn 2026-11-12**, the same stack and rows at SM clock 0.57 of `clocks.max.sm`: every draw
passed on both builds, 6 of 6 each. `n1` was answered `Dein Hund heißt Bello.`, `n2` gave the
French (`Mon numéro d'appartement est quarante-deux.`) inside an English reply, and `n3` was
answered `Your sister's name is Clara.` The sentence leaves a request for another language alone
on these rows. Script: `ask2.sh` in the slot directory above.
