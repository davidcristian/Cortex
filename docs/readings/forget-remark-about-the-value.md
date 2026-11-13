# Readings: a forget's row named only in a remark about the value

How `inside` (`forget_inside.py`) reads a forget message that names a second row only to say
where the value was written or sent. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s; the keep for a row holding the value only
inside a longer value is in [forget-last-group-beside-whole.md](forget-last-group-beside-whole.md).

## What the reader does, 2026-11-13

Over `Remember that my locker code is 4242.` and `Remember that my phone is 0721 555 4242.`, the
call text `4242` and the message `Forget the locker code 4242 that I texted from my phone.`, the
card listed and deleted both rows, since `phone` named the phone row wherever it stood. The same
held for `Oublie le code 4242 du casier, il est noté sur la carte du parc.` and `Forget my gym
code 4242, the one written on the birthday card.` beside a card ending in `4242`.

`asking` (`forget_clauses.py`) returns the message less each remark. A remark is a clause, or the
words of a clause from a relative word after the value (`_RELATIVE`: `that`, `which`, `where`,
`que`, `qu`, `qui`, `dont`, `où`, `donde`, `care`), that holds no forget verb, no clause asking to
keep and not the value. A clause opening with a word of `_AND` (`and`, `or`, `et`, `ou`, `und`,
`oder`, `y`, `o`, `și`, `sau`) takes the role of the one before it, so `Forget the locker code
4242, and the card one too.` still names the card. It reads the
clauses `clauses` splits and the keep openers `parts` reads, so no second clause reader exists.

`inside` reads the row names from `asking`'s part only when that part names a row holding the
value whole; otherwise it reads the whole message, as before. A row that holds the value only as a
group of a longer value and that the remark alone names is then kept, and the card and the reply's
note list it as holding that text only inside a longer value, which is the safe direction. The
part also decides whether `card`, `account` or `IBAN` names a kind (`_KIND`).

`Forget my phone and card numbers ending 4242.`, `Forget the locker code 4242 and the phone that
ends in 4242.` and `Forget that my locker code is 4242 and my phone is 0721 555 4242.` list every
row they name. `Forget 4242 that I texted from my phone.` names no row holding `4242` whole, so it
lists the phone row as before. The tests are `test_forget_side_clause.py`.

A clause list without `and` reads as remarks: `Forget the locker code 4242, the card one.` keeps
the card and shows it in the note. When the part names a card, `_KIND` still lists a row the remark
alone names, as in `Forget the locker code 4242 and the card, I texted both from my phone.`
([task 1185](../refinements/tasks/1185-a-card-word-where-a-forget-asks-lists-a-row-a-remark-alone-names.md)).

## Replay through HEAD and the change

Taken 2026-11-13 at HEAD `22655613b` and the working tree, over 1,534 distinct strings holding a
forget verb (the string literals of every test and doc, the night's proxy log, and the audit's 44
probe messages) and the 27 row sets of
[the word and minus replay](forget-word-and-minus-unnamed.md#replay-through-head-and-the-change)
plus eight: the locker code beside the mobile phone ending `4242` in both orders, the French
locker code beside the card and the phone, the German locker code beside the card, the locker
code beside the card and the phone, the locker code beside a French phone, and the gym code
beside the German card.

| Cases | Changed | Lists more rows | Lists fewer rows | Lists another row |
| --- | --- | --- | --- | --- |
| 340,162 | 48 from 10 strings | 0 | 48 | 0 |

- 44 cases from 8 strings are the remark form: the locker, French and German messages above, each
  keeping the phone or the card, and the gym and card rows of the birthday card message.
- `Oublie le code du casier de la gym, c'est 5521, partout.` keeps the French card, which only the
  `est` of the remark `c'est 5521` named, and `Remember: vergiss meinen Spindcode 8426.` keeps the
  card, which only the remark `Remember` named. Neither message names a card.

The audit's probe (`probe.py`, `cases1.json` to `cases4.json`) changed 9 of its cases, each now
deleting only the row the case wants, and none lists more. The scripts `replay.py`, `strings.py`
and the logs `old.jsonl`, `new.jsonl`, `diff.txt` and `probe_*.txt` are in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot11/`.

## Neighbouring flows on the live stack: rows and the rule

Set in the draw script before any draw. The build is the working tree with the change, run as
`cortexn21-brain-s11side` (memory tools only, like the stack brain), every card approved, every
row deleted before each draw, each fact stored in a chat of its own, and each forget sent from a
new chat unless the row says otherwise.

| Row | Facts stored | Forget turn | Draws |
| --- | --- | --- | --- |
| l | the locker code, `Remember that my mobile phone is 0721 555 4242.` | `Forget the locker code 4242 that I texted from my phone.` | 2 |
| n | the locker code, the mobile phone | `Forget the locker code 4242 and my phone number ending 4242.` | 2 |
| j | `My locker code at the pool is 7319.` | `Actually, forget what I just told you.`, same chat | 2 |
| v | the card, the mobile phone | `Forget 4242.` | 2 |
| o | the gym code | `Forget my gym code.` | 2 |

The rule: l never deletes the mobile phone; n deletes both rows; j deletes the locker row; v
deletes both rows; o deletes the gym code. How often an l call sends the text `4242`, the form the
change reads, is counted apart and fails no item.

## Neighbouring flows on the live stack: what was drawn

Drawn from 06:11 to 06:16 on 2026-11-13, proxy log lines 763 to 849; lines 743 to 762 are a first
pass stopped because its script deleted no row between draws, and are not counted. The SM clock
read 0.58, 0.62 and 0.58 of its maximum before, between and after the draws.

| Row | Call texts | Rows stored after |
| --- | --- | --- |
| l | `4242`; `4242` | the mobile phone, 2 of 2 |
| n | `4242`; `4242` | none, 2 of 2 |
| j | `7319`; `7319` | none, 2 of 2 |
| v | `4242`; `4242` | none, 2 of 2 |
| o | `gym code`; `4242` | none, 2 of 2 |

Every item of the rule holds. Both l calls sent `4242`, 2 of 2, and each card listed the locker
code with the mobile phone under the line for a row holding that text only inside a longer value.
The script `draw.sh`, the logs `draw.log` and `draws.jsonl` and `summ.py` are in the slot directory
above.
