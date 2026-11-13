# Readings: the forget tool on a request to remember a statement in four languages

How `forget_unrequested` (`forget_unrequested.py`) reads a request to remember in French, German,
Spanish or Romanian that a comma or colon follows, then one statement of a fact, such as
`Merke dir, meine Telefonnummer ist 0721 555 019.`, and what a store turn of that message does
when the model calls `forget_memories` unasked. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s; the English statement is measured in
[forget-refusal-english-statement.md](forget-refusal-english-statement.md).

## The German message on the start build and HEAD

Taken 2026-11-13 with `forget_unrequested` alone, no model. The start build `cec7c748f` and HEAD
`a24ecf248` both keep the tool on `Merke dir, meine Telefonnummer ist 0721 555 019.`, so the call
is no regression of the night: `asks_kept_fact_other` read a stated fact only after `que`, `dass`
or `că`, and `asks_kept_other` keeps the tool on any other request to remember in those languages.
Both builds refuse it on `Merk dir, dass meine Telefonnummer 0721 555 019 ist.`. On
`cortexn21-brain-s7kind` (HEAD's brain code) all 4 store turns of the comma form called the tool,
which matched nothing, and the reply closed with the German note for a forget that found nothing
([the draws](forget-kind-and-value-names.md#a-negation-read-per-clause)).

## The reader

`asks_kept_fact_other` also opens a stated fact at a comma or colon after the remember verb when
the rest of the message is one statement in `STATEMENT_OTHER` (`fact_statement.py`), the shape of
the English statement: a possessive (`mein`, `mon`, `mi`, or `meu` after the first noun), at most
six words, a copula (`ist`, `est`, `es`, `está`, `este`, `e` and their plural and past forms) and a
value of at most four words, with no second clause, sentence or obligation of the assistant. The
copulas are new; no verb was added. A request the reader does not read keeps the tool:
`Recuerda,` with a comma is not a request `asks_kept_other` reads (`Recuerda:` and `Acuérdate`
are), and nor is `Retiens,`
([task 1179](../refinements/tasks/1179-a-request-to-remember-read-only-before-que-keeps-the-forget-tool-at-a-comma.md)).

## Replay through the start build, HEAD and the change

Taken 2026-11-13 with no last reply over 33,162 strings: every test string of `brain/`, every
backticked text of `docs/`, the last user message of every request in the night's proxy log, and
74 messages in twelve languages, among them the statement after a remember verb in Italian,
Portuguese, Dutch and Polish (`Ricorda, il mio codice è 4242.`, `Onthoud, mijn code is 4242.`).

| Build | Refused |
| --- | --- |
| start `cec7c748f` | 27,508 |
| HEAD `a24ecf248` | 859 |
| the change | 873 |

14 strings change against HEAD, every one now refused and none now kept: the four drawn store
turns and the new tests' statements after `Merke dir`, `Merken Sie sich`, `Souviens-toi`, `Recuerda:`,
`Acuérdate` and `Ține minte`. No Italian, Portuguese, Dutch or Polish string changes, and no
other backticked docs text. `Merke dir das nicht, vergiss meine Nummer.`, `Recuerda, borra mi código.`,
`Merke dir, wirf meinen Code weg.`, `Merke dir, der Code ist 4242.`,
`Merke dir, meine Nummer ist 0721, danke.` and
`Souviens-toi, mon code est 4242 et jette 1111.` keep the tool. Scripts `replay.sh` and `sep.py`,
logs `start.json`, `head.json`, `new.json` and `diff_head_new.txt`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot8/`,
with the collect, run and diff scripts of `slot3/` beside it.

## The store turn and a forget per language: rows and the rule

Written 2026-11-13 before any draw. The change runs as `cortexn21-brain-s8stmt` (port 23081, the
working tree, memory tools only) through the recording proxy. Per language and draw: empty
`memories`, send the store turn in a new chat, read the rows, then send the forget in a new chat
with every card approved and read the rows again. Two draws per language.

| Language | Store turn | Forget |
| --- | --- | --- |
| German | `Merke dir, meine Telefonnummer ist 0721 555 019.` | `Vergiss meine Telefonnummer.` |
| French | `Souviens-toi, mon numéro de téléphone est 0721 555 019.` | `Oublie mon numéro de téléphone.` |
| Spanish | `Recuerda: mi número de teléfono es 0721 555 019.` | `Olvida mi número de teléfono.` |
| Romanian | `Ține minte, numărul meu de telefon este 0721 555 019.` | `Uită numărul meu de telefon.` |

- **The rule holds** when every forget call of a store turn is refused with `FORGET_UNREQUESTED`,
  every store turn stores the phone row and no store reply holds the note for a forget that found
  nothing, and every forget turn's call runs and leaves no phone row.
- **The change is cleared** when a store turn's call runs, or a forget turn's call is refused.
- A store turn with no forget call decides nothing about the refusal and is counted apart; a
  forget turn whose store turn stored no row is not counted.

## The store turn and a forget per language: what was drawn

Drawn from 04:49 to 04:52 on 2026-11-13, proxy log lines 631 to 686, SM clock 0.58 of
`clocks.max.sm` between draws. The drawn build also took a colon into the opener, which reads
every drawn message the same way.

| Language | Store turns calling the tool | Calls refused | Phone row stored | Forgets deleting the row |
| --- | --- | --- | --- | --- |
| German | 2 of 2 | 2 of 2 | 2 of 2 | 2 of 2 |
| French | 2 of 2 | 3 of 3 | 2 of 2 | 2 of 2 |
| Spanish | 1 of 2 | 1 of 1 | 2 of 2 | 2 of 2 |
| Romanian | 2 of 2 | 2 of 2 | 2 of 2 | 2 of 2 |

**Result: the rule holds.** No store reply holds a note about a forget, and each forget's call ran,
forgot the one row and was confirmed in the reply. Logs `draw.log` and `draws.jsonl`, scripts
`draw.sh`, `summ.py` and `calls.py`, in the slot directory above.
