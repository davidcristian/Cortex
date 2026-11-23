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
