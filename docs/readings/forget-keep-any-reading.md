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
`/home/david/.cache/cortex-run/2026-11-23/f3/`; `replay.sh` takes them again.

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
and `x_broad.json` in `/home/david/.cache/cortex-run/2026-11-23/f4/` (`mkexc.py`, `xcount.py`,
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
