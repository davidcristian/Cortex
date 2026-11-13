# Readings: a forget's row matched by a word, or named after a word for minus

How `kept_rows` (`forget_inside.py`) reads two forms of a forget whose message names one matched
row and not another. The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s; the
same keep for a row holding the value only inside a longer value is in
[forget-group-holder-unnamed.md](forget-group-holder-unnamed.md).

## What the readers do, 2026-11-13

- **A call text holding no digit.** Over `Remember that my gym code is 4242.` and `Remember that
  my bike lock code is 7319.`, `Forget my gym code.` with the call text `code` listed both rows,
  since `unnamed` keeps only a row holding a value of the call's text and `code` holds none.
  `_unnamed_groups` now keeps every row such a text matched that no word or kind word of the
  message names, when one names another matched row, unless the message asks for every row
  (`quantifies`). So the bike lock code stays and the kept note names it. `Forget my codes.`,
  `Forget the code.` and `Forget my gym code and my bike code.` list both rows.
- **A word for minus.** Over `Remember that my card is 4111 1111 1111 4242.` and the gym code,
  `Uită codul 4242 mai puțin cel de pe card.` (forget the code 4242 less the one on the card)
  with the call text `4242` deleted the card and kept the gym code, since no word for minus opens
  a keep clause and `card` names the card row. `_after_minus` keeps every matched row a word after
  a word for minus in its clause names. Its minus words are `MINUS` of `forget_kinds.py`, the set
  `read_kinds` already reads, so no word list grew. The card stays, the gym code stays as before,
  and the kept note names both. `Forget my card 4242 minus the gym one.` lists the card alone.
- **The result.** A delete beside rows kept this way said that they hold the same value and the
  value is still remembered, which is false for `code`. `forgot` (`forget_results.py`) now says
  that they contain that text and were kept, for a call text holding no digit only.

`kept_rows` returns each row once, since `unnamed` beside a clause asking to keep and
`_unnamed_groups` can both keep one (`Forget my gym code, keep the rest.`). The tests are
`test_forget_word_unnamed.py` and `test_forget_minus.py`.

## Replay through HEAD and the change

Taken 2026-11-13 with the replay of the group holder keep over the strings of tests added since
and the night's proxy log, and four more row sets: the gym code beside the bike lock code in both
orders, those two beside the shed padlock code `4242`, and the card beside both.

| Cases | Changed | Lists more rows | Lists fewer rows | Lists another row |
| --- | --- | --- | --- | --- |
| 218,552 | 1,342 from 136 strings | 0 | 1,342 | 0 |

- 948 cases from 130 strings have a call text holding no digit (`code` 880, `card` 68). Each
  keeps a row the message names no word of beside one it names: the bike lock code for `Forget my
  gym code.`, `Oublie mon code de gym.` or `Note that my gym code is now 5555, and forget the old
  one.`, the gym code for `Forget all my bike lock codes.`, and the plain card for messages naming
  the word `other` of `Remember that my other card is 5500 0000 0000 4242.`. 109 are strings of
  earlier tests, 16 of docs and 5 of tests added since that replay; no proxy log string changes.
- 394 cases from 6 strings hold a word for minus (`minus`, `less`, `moins`, `menos`,
  `mai puțin`), and each keeps the card or the gym row named after that word; with the call text
  `code`, `Forget my card 4242 minus the gym one.` also keeps the bike lock and shed codes, which
  no word names.

The scripts `replay.py`, `summ2.py` and the logs `old.jsonl`, `new.jsonl` and `diff.txt` are in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot7/`.

## Neighbouring flows on the live stack: rows and the rule

Set in the draw script before any draw. The build is the working tree with the change, run as
`cortexn21-brain-s7word` through the recording proxy on the `cortexn21` stack (memory tools only,
like the stack brain), every card approved, every row deleted before each draw, each fact stored
in a chat of its own, and each forget sent from a new chat unless the row says otherwise.

| Row | Facts stored | Forget turn | Draws |
| --- | --- | --- | --- |
| w | the gym code, the bike lock code | `Forget my gym code.` | 2 |
| r | the card, the gym code | `Uită codul 4242 mai puțin cel de pe card.` | 2 |
| j | `My locker code at the pool is 7319.` | `Actually, forget what I just told you.`, same chat | 2 |
| v | the card, `Remember that my mobile phone is 0721 555 4242.` | `Forget 4242.` | 2 |
| c | the gym code, the bike lock code | `Forget my codes.` | 2 |
| o | the gym code | `Forget my gym code.` | 2 |

The rule: w never deletes the bike lock code; r never deletes the card; j deletes the locker row;
v and c delete both rows; o deletes the gym code. How often a call sends the text `code` alone
(w, c) or `4242` (r), the forms the change reads, is counted apart and fails no item.

## Neighbouring flows on the live stack: what was drawn

Drawn from 04:13 to 04:19 on 2026-11-13, proxy log lines 488 to 604. The SM clock read 0.58,
0.58 and 0.65 of its maximum before, between and after the draws.

| Row | Call texts | Rows stored after |
| --- | --- | --- |
| w | `gym code`; `4242` | the bike lock code, 2 of 2 |
| r | `gym code`; `gym code` | the card, 2 of 2 |
| j | `7319`; `7319` | none, 2 of 2 |
| v | `4242`; `4242` | none, 2 of 2 |
| c | `4242`, `7319`, `bike lock code`, `gym code`, in both | none, 2 of 2 |
| o | `4242`; `gym code` | none, 2 of 2 |

Every item of the rule holds. No call sent `code` alone or `4242` for r, so neither reader was
drawn: 0 of 4 and 0 of 2. In c both draws first sent the two values, which the message names no
word of, so `unnamed` kept each row as it does at HEAD and the model then sent the two names. The
drawn build still listed a row a word before the word for minus also named, which no drawn
message holds. Scripts `draw.sh`, logs `draw.log` and `draws.jsonl`, in the slot directory above.
