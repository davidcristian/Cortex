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
the card and shows it in the note. When the part names a card, an account or an IBAN (`_KIND`),
the kind word lists every row holding the value as a group, except a row that a word of the
message outside the part names and the part does not (`_grouped`). So `Forget the locker code
4242 and the card, I texted both from my phone.` lists the locker and card rows and keeps the phone
row, shown in the note, while `Forget my card 4242.` beside the phone row still lists the card.

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

## A kind word beside a remark: replay through HEAD and the change

Taken 2026-11-13 at HEAD `f27d46da5` and the working tree, over 1,544 distinct strings holding a
forget verb (the sources above, the test strings of the tree, the proxy log to line 992 and five
forms of the kind word message) and the row sets above.

| Cases | Changed | Lists more rows | Lists fewer rows | Lists another row |
| --- | --- | --- | --- | --- |
| 342,466 | 24 from 3 strings | 0 | 24 | 0 |

Each change keeps the mobile phone or the French phone ending `4242`, beside the locker code alone
or with the card, for `Forget the locker code 4242 and the card, I texted both from my phone.`,
`Forget the card and the locker code 4242, I read both on my phone.` and
`Forget the locker code 4242 and my card, the ones I sent from my phone.`. No case outside that
form changes, the neighbouring flows above among them, so no draw was taken.
`Forget the card 4242, the one I read from my phone.` and
`Forget 4242 and my card, I sent the code from my phone.` still list the phone row, since their
asking part names no row holding `4242` whole and `inside` reads the whole message
([task 1189](../refinements/tasks/1189-a-remark-beside-no-whole-row-lists-the-row-it-names.md)).
The scripts `replay2.sh` and `strings.json` and the logs `old2.jsonl`, `new2.jsonl` and
`diff2.txt` are in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot13/`,
with `replay.py` in `slot11/` beside it.

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

## A remark beside a row holding the value as a group

Taken 2026-11-14 for
[task 1189](../refinements/tasks/1189-a-remark-beside-no-whole-row-lists-the-row-it-names.md).
The remark reader read the part asking to forget only when it named a row holding the text whole,
so `Forget the card 4242, the one I read from my phone.` beside a card and a phone ending `4242`
deleted the phone, which only the remark names. The change reads that part when it names a row
holding the text whole or as a group, and keeps a row holding the text as a last group that a
word of the message names and no word of that part names.

**Replay.** Every string literal of the brain's forget test files and every backticked string of
`docs/readings/` (3,493 messages) went through the card and the delete, every card approved, with
the text `4242`, over 21 row sets: each pair and triple of a locker code, a gym code, a phone
`0721 555 4242`, a card `4111 1111 1111 4242` and a row holding an alarm code beside a bike lock
`4242`, and all eight rows of the side clause tests. Of 73,353 cases, the build before the change
and the change differ in 28 rows, each kept by the change and deleted before it, and in no row
deleted by the change and kept before it. The 28 come from 8 messages: 24 phone rows of six
messages with a remark naming the phone, and 4 card rows of two stored replies about an old phone
number. The script `replay.py` and the logs `replay-old.jsonl` and `replay-new.jsonl` are in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/11450320-079c-401d-9f26-43a763a369b6/scratchpad/slot1/`.

**Live rows and the rule**, set before any draw. Builds `cortexn22-brain-head` (the tree before the
change) and `cortexn22-brain-s1fix` (the working tree with it), every tool listed, through the
recording proxy, every card approved, every row deleted before each draw, each fact stored in a
chat of its own, each forget sent from a new chat unless the row says otherwise.

| Row | Facts stored | Forget turn | Build | Draws |
| --- | --- | --- | --- | --- |
| r | `Remember that my card is 4111 1111 1111 4242.`, `Remember that my mobile phone is 0721 555 4242.` | `Forget the card 4242, the one I read from my phone.` | both | 2 each |
| j | `My locker code at the pool is 7319.` | `Actually, forget what I just told you.`, same chat | change | 2 |
| v | the card, the mobile phone | `Forget 4242.` | change | 2 |

The rule: r on the change never deletes the mobile phone; j deletes the locker row; v deletes both
rows. r on the build before the change shows what the change alters and fails no item, and so does
how often an r call sends the text `4242`.

**Live draws.** Drawn from 23:48 to 23:53 on 2026-11-13, proxy log lines 52 to 133. The SM clock
read 0.58, 0.65 and 0.71 of its maximum before, between and after the draws.

| Row | Build | Call texts | Rows stored after |
| --- | --- | --- | --- |
| r | before the change | `4242`; `4111 1111 1111 4242` | none; the mobile phone |
| r | the change | `4111 1111 1111 4242`; `4111 1111 1111 4242` | the mobile phone, 2 of 2 |
| j | the change | `locker code at the pool is 7319`; `locker code` | none, 2 of 2 |
| v | the change | `4242`; `4242` | none, 2 of 2 |

Every item of the rule holds. An r call sent `4242`, the form the change reads, in 1 of 4 draws,
on the build before the change, whose card listed the card and the mobile phone and deleted both;
the change met the form only in the replay. The scripts `draw.sh` and `driver.py` and the logs
`draw.log` and `draws.jsonl` are in the slot directory above, `driver.py` one level up.
