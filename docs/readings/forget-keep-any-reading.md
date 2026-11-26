# Readings: a row any reading of a keep clause names

How the forget card reads a keep clause that names a row in more than one way: the row to forget
named again beside other words (`Forget the card 4242, keep only the card.`), two rows sharing a
word (`keep the card and my new card`), or a row word in another number (`Forget all 4242 but the
lockers.`). The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s; `may_keep`
(`forget_inside.py`) and `reads` (`forget_kinds.py`) implement it.

## The replay, 2026-11-23

Unit calls through `ForgetChosenTool`, each case over its own rows with the call text it names.
The instrument is the generator of the forget card replays: 42,356 generated messages (4 opening
forms, then one or two of 7 kinds of clause over 3 rows, in the 5 note languages), 5,175 extra
forms with what each message asks of every row, and 10,385 calls over the strings of the brain's
forget tests, which have no such record. The extras include, for this change:

- 12 calls naming the row to forget again beside a word naming no row (`keep only the card`,
  `keep just the card`, `keep my old card`) and the near misses `I don't need the card` and
  `I don't want the card anymore`, and 2 calls of `Forget my phone 4242 but keep Anna's phone.`
  over a row for Anna's phone.
- 796 calls over two rows sharing a word, an English card and new card and their Spanish forms:
  the 4 opening forms with one clause of each kind, either card first, and the messages naming
  both cards or one in the keep clause.
- 6 calls with a plural row word after a word for all, and 4 of their near misses.

The listings are `cmp_final.txt`, `costs_final.txt`, `full_before.json` and `full_final.json` in
`~/.cache/cortex-run/2026-11-23/f3/`; `replay.sh` takes them again.

| | before | after |
| --- | --- | --- |
| rows the message asks to keep that the card lists | 36 | 0 |
| rows newly listed | | 0 |
| rows newly kept that the message asks to keep | | 36 |
| rows newly kept either way | | 386 |
| rows newly kept that the message asks to delete | | 91 |
| rows newly kept over the test strings | | 104, in 17 strings |

The 36 listed before were 22 plural row words in a keep form after a word for all
(`Oublie tous les 4242, le casiers reste.`), 6 of the task forms with `lockers`, 6 keep clauses
naming two cards that share a word and 2 of `keep only the card` and `keep just the card`.

The 91 rows asked to delete that are now kept:

- 44 in 12 messages keeping a plural row word in a clause no reader reads after a word for all,
  as `Forget all 4242, the lockers stays.`, which now keeps all three rows, as
  `Forget all 4242, the locker stays.` did before.
- 36 in 33 messages forgetting one of two cards and keeping the other by a longer name, as
  `Forget my old card 4242, keep the new card.` and `Forget the card 4242, keep my new card.`,
  which now keep both cards.
- 6 in 6 Romanian messages keeping `dulapul` after `exceptând`, as
  `Uită 4242 de pe card exceptând dulapul, dulapul rămâne.`, which now keep the card too.
- 4 in 2 messages with a negation before a verb other than a keep verb, which the card reads as
  a clause asking to keep: `Forget the card 4242, I don't need the card.` and
  `I don't want the card anymore`.
- 1 of `Forget my phone 4242 but keep Anna's phone.`, which now keeps the phone.

The 17 test strings are the same forms: Anna's phone or card (5), a negation before another verb
(4, with the Romanian `nu vreau cardul`), the old and new card (3), and 5 Romanian strings keeping
`cartela` or `consulul`, of which `Uită cardul 4242, păstrează consulul și cardul.` asks to keep
the card.

A word one or two letters longer than a function word of a row names nothing here: `queda` less
two letters is `que`, which every Spanish row holds, so `reads` compares a longer word only with
the words of a row's request that are no function word. Compared with every word of the row, the
same rule kept 104 more generated rows asked to delete, as the card of `Olvida 4242 de la
tarjeta, conserva el gimnasio, el gimnasio se queda.`.

`forget_named` (`forget_keep_named.py`) reads a longer word of a part asking to forget the same
way, so `Olvida el código del gimnasio que queda.` with the call text `tarjeta` deletes no card.
Over the same replay that changed 4 calls and no generated message: `Oublie ce que je viens de
dire.` and `Oublie ce que je viens de te dire.` beside German rows, whose request holds `dir`,
list the card and the phone the call texts `card` and `phone` name, 8 rows, as each did before
the longer word reading. The listing is `cmp_f3vf2.txt` in the same folder.

## An exception that follows no forget verb, 2026-11-23

`after_but` reads a word for but only after a forget verb and only in a clause with no forget verb
after it, and `after_value` reads only words naming a row by a word it holds or a kind word. In
`All 4242 but my lockers, forget them.` only the exception role of `beside` keeps the locker, and
`may_keep` takes that role from the runs read with the longer words among the words naming a row.
The replay adds 76 calls to the generator: 19 messages in the five note languages, a plural or
definite row word after a word for but with no forget verb before it or one after it in its
clause, each with the call texts `4242` and the three row words. The listings are `x_after.json`
and `x_broad.json` in `~/.cache/cortex-run/2026-11-23/f4/` (`mkexc.py`, `xcount.py`,
`exc.sh`).

| | before | after |
| --- | --- | --- |
| of the 76 calls, those listing a row the message asks to keep | 22 | 0 |
| of the 76 calls, rows listed that the message asks to delete | 50 | 50 |
| two generators' 57,916 and 57,096 calls and 16,872 word pair cases, rows changed | | 0 |

The 22 are English (12), German (6) and French (4); no Spanish or Romanian call listed the row
to keep. The word pair cases are those of
[the longer forget word readings](forget-longer-word-beside-a-value.md). With the exception role
left out of `may_keep`, a forget test fails on `All 4242 but my lockers, forget them.` beside a
row holding `lockers` and `4242` inside a longer value, which no other reader of `may_keep` keeps.

## An item after a keep clause, 2026-11-24

`parts` reads a clause with no forget verb after a keep clause as part of it only when it reads
that keep clause itself, which needs a keep verb, a word for except or a negation; `bleibt` is a
keep verb. After a clause only another reader keeps (`kept_again` for `the phone stays`, `le
téléphone reste` and `dulapul rămâne`, `after_but` for `the card but the phone`), an item such as
`the locker too` was read as adding a row, and the card deleted it. `after_kept`
(`forget_clauses.py`) returns the words of each clause with no forget verb after a clause holding,
past its last forget verb, a word a reading of `may_keep` keeps (or `kept_again` with the longer
words), and `may_keep` keeps the rows they name. So `Forget 4242, the card, the phone stays, the
locker too.`, `Forget 4242, the card but the phone, the locker too.`, `Oublie 4242, la carte, le
téléphone reste, le casier aussi.` and `Uită 4242, cardul, dulapul rămâne, și telefonul.` keep the
locker, and so does each with a later clause keeping the phone again, as `Forget the card 4242 but
the phone, the locker too, keep the phone.`. The tests are `test_forget_after_keep.py`.

How each near miss is read:

- `Forget the card 4242, the phone stays, forget the locker 4242 too.`, the same with a full stop,
  and `Keep the phone, forget the card, the locker too.` ask to delete the locker, since its clause
  has a forget verb. The card deletes it.
- `Forget the card 4242, the phone too, keep the card.` asks to delete the phone. The later clause
  keeps the card word of the first clause, so the phone is kept too, a cost. Starting nothing at a
  clause whose kept word a later clause holds deletes this phone and keeps 383 fewer rows asked to
  delete, but deletes the item of 1,314 of the 22,758 messages keeping a word again below, as the
  locker of `Forget the card 4242 but the phone, the locker too, keep the phone.`.
- `Forget the card 4242, the phone, I think, the gym too.` asks to delete the gym. The phone's own
  run has a role read; a role a later clause leaves unread starts nothing. Taking those roles too
  kept 628 rows asked to delete against 616, and failed this test.
- `Forget the card but not the phone, and the locker too.` can add the locker to the forget or to
  the negation, so it is read both ways and the locker is kept, as `parts` already did.

The replay adds the audit's 6,156 mixed cases (`x-mix`) and 1,104 near misses with a forget verb
before the item after each keep clause to the generator, 71,332 calls with 10,865 over the strings
of the forget tests, and runs the 12,768 word pair and 4,104 valued cases of the 2026-11-23 audit
and 22,758 messages naming the kept word again in a later clause that keeps it, built from the
rows' own words in the five note languages (`again.py`).

| | before | after |
| --- | --- | --- |
| of the mixed cases, rows asked to keep that the card deletes | 190 | 0 |
| of the messages keeping a word again, rows asked to keep that the card deletes | 1,584 | 0 |
| of the generator's other calls, rows listed that the message asks to keep | 0 | 0 |
| rows newly listed, every case | | 0 |
| rows asked to delete that are newly kept | | 616 |

Of the 616, 233 are an item after a word for only the readers leave unread (`seulement`,
`juste`, `nur`, `doar`; French 120, German 80, Romanian 20), as `Oublie 4242, seulement la carte,
le téléphone aussi.`, and 13 after Romanian `de asemenea`, which `_ADD` lacks. `kept_again` keeps
the row of that clause, so the rule keeps the item after it. The other 383 are an item between a
head naming a row and a later clause keeping that row (English 204, French 88, German 80,
Romanian 11), as the phone of `Forget the card 4242, the phone too, except the card.`. The near
misses changed in no row. The scripts `f3gen/mixforms.py`, `replay.sh`, `cmp7.py` and
`costform.py` are in `~/.cache/cortex-run/2026-11-24/f7/`, and `again.py`, `again2.py`,
`replay.sh`, `recount.py` and the listings `f3_after.json`, `again_before.json` and
`again_after.json` in `~/.cache/cortex-run/2026-11-24/a2/`.

## A negation inside a clause with a forget verb, 2026-11-24

`opens_keep` (`forget_clauses.py`) read a negation as opening a keep clause only when it opened
its clause or followed a leading word such as `but`, `do`, `mais` or `aber`. French and German
write it after the forget verb, and German also at the end of the clause, so `Oublie 4242,
n'efface pas la carte.`, `Oublie 4242. N'oublie pas la carte.`, `Vergiss 4242, lösch nicht die
Karte.`, `Vergiss 4242, vergiss die Karte nicht.` and `Vergiss 4242. Lösche die Karte nicht.`
listed the card. A negation now opens a keep clause anywhere in a clause holding a forget verb,
unless a word for the or my is one of the two words before it. One just before or after a forget
verb, or ending its clause (`_negates`), also keeps the words before it back to that forget verb,
the verb included, or to a joining word, as a keep verb does. No word was added to a list. So the
five messages keep the card, and so do `Vergiss 4242 und die Karte nicht.`, `Vergiss 4242, die
Karte nicht löschen.` and `Je ne veux pas oublier la carte, oublie 4242.`. The tests are
`test_forget_negated_verb.py`.

How each near miss is read:

- `N'oublie pas d'effacer la carte.` asks to delete the card. Its one clause negates a forget verb
  and names the card, so the card is kept, a cost. `Vergiss nicht, die Karte zu löschen.` has its
  forget verb in a clause of its own, and the card is kept before and after, as in a message
  lacking the value.
- `Vergiss nicht nur 4242, sondern auch die Karte.` asks to delete every row holding `4242`. Its
  first clause negates `vergiss` and the second joins it, so every row is kept, as before.
- `Forget 4242 on the card I no longer use.` and `Forget 4242 on the card I do not use.` ask to
  delete the card. The negation opens its keep clause where it stands, with no row word after it,
  so the card is deleted; the first kept it before, through `after_value`.
- `Oublie 4242 sur la carte que je n'utilise jamais.` and `Lösche 4242 von der Karte die ich nicht
  mehr brauche.` ask to delete the card, and it is kept before and after.
- `Forget the not so new shed padlock code 7319.` names a fact: `not` follows `the`.
- `Forget all 4242 though not the card.` keeps the card as before, and `though` is now a run of
  its own that no reader reads, so the phone and the locker are kept too.
- `Forget 4242 not the card.` keeps the card and now deletes the locker, which it asks to delete;
  before, no reader read the words after the value and every row was kept.

The replay runs the audit's 8,376 messages with a negated forget verb (the generator's four heads,
the negated tails of the five languages and an adding tail, singly and in pairs, with `4242`, `42
42` or `4 2 4 2`), 21 calls over the forms and near misses above, the generator's 71,332 calls,
the forget of everything family's 3,864, the 6,156 mixed cases, and the 12,768 word pair and 4,104
valued cases of the 2026-11-23 audit.

| | before | after |
| --- | --- | --- |
| of the audit's negated messages, rows asked to keep that the card lists | 3,264 | 0 |
| of the 21 forms and near misses, rows asked to keep that the card lists | 9 | 0 |
| of the generator's calls, rows listed that the message asks to keep | 0 | 0 |
| of the other four sets, rows newly listed or newly kept | | 0 |
| over the strings of the forget tests, rows newly listed | | 10 |
| rows asked to delete that are newly kept | | 249 |

The 10 are the code rows of `Forget 4242 not the card.` and its lowercase form, which the message
asks to delete; none is a card. The 51 rows newly kept over the test strings are those of `I have
not removed anything from my memory.`, which asks for nothing. Of the 249, one is the card of
`N'oublie pas d'effacer la carte.`, 212 are a forget of every value (`Vergiss alle 4242, lösch
nicht die Karte.`; German 180, French 32), which now keeps every row as `Oublie tous les 4242, ne
supprime pas le casier.` and `Forget all 4242, don't delete the locker.` already did
([R-1336](../refinements/tasks/1336-a-forget-of-every-value-beside-a-negated-forget-verb-keeps-every-row.md)),
and 36 are a German message naming the card both to forget and to keep. The change also deletes
175 rows asked to delete that were kept, as the locker of `Oublie 4242, n'efface pas la carte.`.
The scripts `mknear.py`, `replay.sh` and `cmp.py` and the listings are in
`~/.cache/cortex-run/2026-11-24/f10/`, the audit's `mkneg.py` in `a3/`.

## A forget verb inside a keep clause, 2026-11-25

A keep clause holding a forget verb, as `lösch nicht die Karte` after `Vergiss alle 4242`, read
that verb as a word naming a fact, and since it names no stored row the clause was read in part
and every row was kept. The words a keep clause names (`_split` in `forget_unnamed.py`) now leave
out a forget verb as they leave out a keep verb, so the clause names its row as `nicht die Karte`
does. No word was added to a list. Replayed over the same sets as above, the tree before the
change against the tree after it:

| Case set | Cases | Rows asked to keep listed | Rows newly listed | Rows asked to delete newly kept |
| --- | --- | --- | --- | --- |
| the audit's negated messages | 8,376 | 0 before and after | 208, each asked to delete | 0 |
| the generator, the family, mixed, pairs and valued | 98,224 | 222 before and after, all in the family | 0 | 0 |

The 208 rows now deleted are German 96, Spanish 76 and Romanian 36, as the locker code of
`Vergiss alle 4242, lösch nicht die Karte.`, `Olvida 4242, no borres la tarjeta.` and `Uită
4242, nu uita cardul.`. French and English are unchanged: `Oublie tous les 4242, n'efface pas le
casier.` keeps every row as `Oublie tous les 4242, pas le casier.` does, and `Forget all 4242,
don't delete the locker.` reads `don` in the part asking to forget and keeps every row, as
`Forget all 4242, not the locker.` does
([R-1342](../refinements/tasks/1342-a-forget-of-every-value-beside-a-french-or-english-negated-keep-clause-keeps-every-row.md)).
The scripts and listings are in `~/.cache/cortex-run/2026-11-25/f2/`.

## A contracted negation, 2026-11-26

`parts` (`forget_clauses.py`) now reads the word just before a negation of one letter, as `don` of
`don't`, inside the keep clause it opens, and `_split` reads no fact in it, as `do` of `do not`
names none. No word was added to a list. Replayed tree against tree: no row asked to keep is newly
listed over the generator, the family, the mixed messages, the word pairs, the valued cases, the
negated messages or the 13,827 mixed builder cases; 312 rows asked to delete are now deleted in 288
English negated messages, as the phone and the locker of `Forget all 4242, don't delete the card.`,
and 30 in the mixed builder cases. Scripts: `replay.sh`, `m25.sh` and `cmp.py` in
`~/.cache/cortex-run/2026-11-26/f1/`. `held` (`forget_inside.py`) reads no fact in it either: 10
more rows asked to delete are deleted in the 44 `Don` cases, as Don's row of `Forget Don, don't
remove the card.`, and no row asked to keep is newly listed (`~/.cache/cortex-run/2026-11-26/x1/`).
