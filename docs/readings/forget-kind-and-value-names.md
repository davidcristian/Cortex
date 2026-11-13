# Readings: kind words across languages and a value alone beside a keep clause

How `unnamed` (`forget_unnamed.py`) and the last group keep (`_ends` in `forget_inside.py`) read
two forms that kept every row at the start build `cec7c748f`: a forget naming a row only in words
of another language than the row's, and a forget part naming only a value beside a clause asking to
keep. The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s; the earlier keep
clause forms are in [forget-keep-clause.md](forget-keep-clause.md) and
[forget-keep-except.md](forget-keep-except.md).

## What the readers do, 2026-11-13

- **Kind words.** `forget_kinds.py` holds a closed table of two kinds in the five note languages:
  `card`, `carte`, `Karte`, `Kreditkarte`, `tarjeta`, `cardul` and their plurals, and `phone`,
  `téléphone`, `Telefon`, `teléfono`, `telefonul`. A message word of one kind names a row holding a
  word of the same kind, beside the rule that a word both hold names the row. `Telefonnummer` names
  the phone row through its stem `telefon`. The table is read where `unnamed` and the last group
  keep compare the message's words with a row's, and nowhere else.
- **Kinds never list a row in a message holding a negation or a word for minus** (`read_kinds`:
  a word of `NOT` in `forget_clauses.py`, or `minus`, `less`, `moins`, `menos`, `weniger`,
  `puțin`), since `N'oublie pas ma carte.` and `Oublie le code 4242 moins celui de la carte.` name
  the card as a row to keep, and no keep clause opens there. Such a message still reads a kind as
  naming a row where that only keeps rows: it ends the newest row exception and the forget of
  every row.
- **A value alone beside a keep clause.** When the part outside the clause names no word and each
  content word of the clause, less the function words of the reading, names a matched row, the
  part's whole values name each matched row whose request holds one of them as its whole value.
  So `Forget every 4242 except the card.` lists the gym code `4242` and keeps the card, which holds
  `4242` only as its last group, and `Forget 4242 except my gym code.` keeps both. A clause with a
  word that names no matched row (`except the phone` with no phone row, `keep it quiet`,
  `behalte die vom Schuppen` over English rows) keeps every row, as before.

The tests are `test_forget_kinds.py` and `test_forget_keep_value.py`.

## Replay through the start build and the change

Taken 2026-11-13. 1,419 distinct strings holding a forget verb, from the string literals of the
brain's tests (1,096), the backticked text of `docs/` (500), the user messages of the night's proxy
log and the language list of an earlier slot. Each went through `ForgetChosenTool.card` and
`invoke` over 14 fixed row sets (an English, French and German card ending in `4242`, an English
gym code `4242`, an English and German phone `0721 555 019`, an IBAN and an English mobile phone
`0721 555 4242`, alone and in pairs and threes) with the call texts `4242`, `4111 1111 1111 4242`,
`0721 555 019`, `code`, `card`, `phone` and the string's own values, each only where a row holds
it, plus four sets of rows holding the string's last value (bike, shed, gym, `Fahrradcode` and
card rows) with that value and `code`, from the chat that stored the rows and from a new one.

| Cases | Changed | Lists more rows | Lists fewer rows | Lists another row |
| --- | --- | --- | --- | --- |
| 125,264 | 705 from 120 strings | 575 | 121 | 9 |

- **Lists more, by kind (357 cases, 80 strings).** Each is a message naming a row's kind in
  another language than the row's: `Vergiss meine Telefonnummer 0721 555 019.`, `Lösch meine
  Telefonnummer.`, `Supprime mon numéro de téléphone.`, `Oublie ma carte.`, `Vergiss die Karte, die
  auf 4242 endet.` over the English rows, and English messages such as `Forget my card 4242.` and
  `Forget my phone number.` over the French and German rows, which the start build already listed
  for the English row of the same message.
- **Lists more, by value (218 cases, 23 strings).** Each is a forget part naming only a value
  beside a clause each of whose words names a matched row: `Forget every 4242 except the card.`,
  `Forget every 4242 but keep the card.`, `Forget the code 4242 except the card.`, `Oublie tous les
  4242 sauf la carte.`, `Forget 7319, keep the shed one.`, `Vergiss 7319, behalte den Fahrradcode.`
  and `Forget every 4242 except the phone.` beside a mobile phone row. Every added row holds the
  value as its whole value and is named by no word of the clause; no card holding it as a group is
  added.
- **Lists fewer (121 cases, 37 strings).** A kind word now names a row, so the message no longer
  reads as asking for every row and the newest row exception ends: `Forget my card 4242.` over the
  French card beside the gym code deleted both rows and now deletes the card alone, and
  `N'oublie pas ma carte.` no longer deletes the gym code the chat stored last.
- **Lists another row (9 cases, 5 strings).** `Oublie ma carte.`, `Oublie la carte qui finit par
  4242.` and two German card forgets in the chat that stored the rows deleted the newest row (the
  gym code or the mobile phone) and now delete the card they name.

No change lists a row that the message does not name by a word, a kind or its whole value. Both
builds list a mobile phone `0721 555 4242` beside the card for `Forget the card ending in 4242.`
with call text `4242`, since neither row holds `4242` whole; the reader that keeps the phone is in
[forget-group-holder-unnamed.md](forget-group-holder-unnamed.md). Scripts
`replay.py` and `diff.py`, the logs `old.jsonl` and `new.jsonl` and the per case list `diff.txt`
are in `/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot4/`.

## Neighbouring flows on the live stack: rows and the rule

Written before any draw. The build is the working tree with the change, run as
`cortexn21-brain-s4kind` through the recording proxy on the `cortexn21` stack (memory tools only,
like the stack brain), every card approved, every row deleted before each draw, and each fact
stored in a chat of its own.

| Row | Facts stored | Forget turn | Draws |
| --- | --- | --- | --- |
| j | `My locker code at the pool is 7319.` | `Actually, forget what I just told you.`, same chat | 2 |
| v | `Remember that my card PIN is 7319.`, `Remember that my door code is also 7319.` | `Forget 7319.` | 2 |
| o | `Remember that my gym code is 4242.` | `Forget my gym code.`, a new chat | 2 |
| x | `Remember that my card is 4111 1111 1111 4242.`, `Remember that my gym code is 4242.` | `Oublie la carte qui finit par 4242.`, a new chat | 2 |

The rule: in j every draw that calls a forget tool deletes the locker row; in v every draw that
calls one with the text `7319` deletes both rows; in o every draw that calls one deletes the gym
row; in x no card lists the gym row and the gym row is stored after every draw. A draw with no
forget call is counted apart and fails no item.

Added after the second j draw stored no row, before the draw it adds: one more j draw, j3, which
replaces a j draw whose store turn kept no row, under the same rule.

## Neighbouring flows on the live stack: what was drawn

Drawn from 03:10 to 03:14 on 2026-11-13 on `cortexn21-brain-s4kind`, proxy log lines 320 to 394.
A first pass at lines 251 to 319 lost its row reads to a wrong column name and is not counted. The
SM clock read 0.58 to 0.59 of its maximum between draws.

| Row | Draws with a forget call | Call text | Rows stored after |
| --- | --- | --- | --- |
| j | 2 of 2 reached (j1, j3) | `7319` | none, 2 of 2 |
| v | 2 of 2 | `7319` | none, 2 of 2 |
| o | 2 of 2 | `4242` | none, 2 of 2 |
| x | 2 of 2 | `4111 1111 1111 4242` | the gym row, 2 of 2 |

Every item of the rule holds. In j2 the store turn itself called `forget_memories`, which matched
no row, so the reply kept nothing in memory and the forget turn's call matched nothing; j3
replaced it. In x both calls sent the whole card number, which the gym row does not hold, so the
card listed the card row alone and deleted it; at the start build the same call keeps the card,
since `carte` names no word of the English row. No x draw sent `4242`, so the card beside the gym
code by its last group was not drawn. Scripts `draw.sh`, `draw3.sh` and `summ.py`, logs `draw.log`
and `draws.jsonl`, in the slot directory above.

