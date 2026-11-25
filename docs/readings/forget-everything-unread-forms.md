# Readings: a forget of everything in a form the card does not read as one

How the forget card treats a message that asks to forget every row and to keep one, in a form
that `everything` (`forget_permit.py`) does not read: no clause mark before the kept row, no
forget verb, or a word for all that no cell of the table of forms (`forget_forms.py`) holds. The
decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s. The forms the card does read
are in [forget-everything-unread-role.md](forget-everything-unread-role.md). The last
section counts what the model does with two such messages on the stack.

## The generated family, 2026-11-24

Over the generator's three rows in each of five languages (a card, a phone and a locker code,
each holding `4242`), with the call text `4242` and with each row's own word. Each message asks
to forget every row and keeps one, in each of the generator's keep clauses (except, but, keep,
stays, not) and six more per language: the stays clause with no clause mark, as in `Forget
everything the card stays.`, and `leave`, `apart from`, `à part`, `bis auf`, `menos` and `în
afară de`. That is 3,468 cases over 846 messages, each case with one row asked to keep. The rows
asked to keep that the card lists, on the tree of this date:

| Head | Clause mark before the kept row | Messages | Rows asked to keep | Listed |
| --- | --- | --- | --- | --- |
| read, as `Forget everything`, `Oublie tout`, `Olvida todas` | yes | 213 | 852 | 0 |
| read | no | 96 | 432 | 66 |
| word for all unread, as `Vergiss alles`, `Olvida todo`, `Uită tot`, `Uită totul` | yes | 174 | 696 | 28 |
| word for all unread | no | 96 | 384 | 60 |
| no forget verb, as `Wipe everything`, `Everything must go`, `Alles muss weg` | yes | 183 | 732 | 90 |
| no forget verb | no | 84 | 372 | 96 |

Of the 340 rows listed, 158 are listed for the call text `4242` and 182 for the kept row's own
word. `Forget everything the card stays.` lists the card alone for `4242`: `the card` opens as a
limit does. `Olvida todo, la tarjeta se queda.` lists the card only for `tarjeta`, since the
words after the call text in the message name no row.

The family also writes near misses: 51 messages asking to forget one row with a word for all,
such as `Forget everything the card holds.`, `Forget all card numbers.`, `Olvida todo sobre la
tarjeta.`, `Vergiss alles über die Karte.` and `Uită tot despre card.`, and five naming no stored
row, such as `Forget my todo list.` and `Vergeet 4242 tot morgen.`.

## Two rules replayed, 2026-11-24

Both keep a row named in a run whose role no reader reads (`kept_again` in `forget_clauses.py`),
with the runs read as the runs after a value are, from the first forget verb or, in a message
with none, from its first word. Each was replayed over the family, the generator of the previous
night's forget slots (71,332 cases, with the test literals), the a1 word pairs (12,768) and the
valued cases (4,104). Rows asked to keep still listed, and rows asked to delete newly kept:

| Runs read | Keep rows listed in the family | Newly kept: family | Generator | Pairs and valued |
| --- | --- | --- | --- | --- |
| from the first forget verb, its own clause included | 0 | 92 | 1,411 | 0 |
| only the clauses after that verb's clause | 222 | 0 | 0 | 0 |

The first rule makes every form above fail safe. It also keeps the row of every near miss naming
one, in 47 messages such as `Forget everything the card holds.` and `Forget all card numbers.`,
and of 1,198 generated messages such as `Forget all 4242 and the card.`, and 389 rows the
generator marks as either way. With no new word read, `my card stays` differs from `my card
holds` only by a word no reader reads, so no rule keeps one without the other.

The second keeps the rows of every form with a clause mark, 118 of the 340, and 3 rows asked
to keep in the valued cases, as the locker code of `Forget my lockers 1234, the locker stays.`.
It names rows only from those the call lists, so a row a later clause adds is read as unread: it
keeps 24 rows asked to delete in 7 forget messages of the test literals, as the phone of `Forget
the locker code 4242, the phone and the card too.` for the call text `phone`. The near misses
list what they listed before under both rules. Neither rule is built.

Scripts: `f3gen/every.py` (the family), `ecount.py`, `ebreak.py`, `gtable.py`, `delta.py` and
`replay4.sh` in `~/.cache/cortex-run/2026-11-24/f4/`; the generator is `f3gen/` there.

## Drawn on the stack brain, 2026-11-24

The rule, written before the launch: a message keeps its premise when at least 3 of its 4 draws
make no forget call, and a row the message keeps that a draw deletes is a defect. Project
`cortexn29`, the brain image built from the tree at this date with its core bound, the model host
`cortex-model-host` on engine build `b12375` with the tree's core and model manager bound, compose
defaults, `judge` recall, through the recording proxy (lines 12 to 36). The cortex argv:
`unsloth/gemma-4-12B-it-qat-GGUF/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, context 16384, no cache
type flag, the MTP drafter `mtp-gemma-4-12B-it-Q8_0.gguf` with at most 3 drafted tokens, and
reasoning budget `-1` with no reasoning effort set. The four rows of
[the earlier draw](forget-everything-unread-role.md#drawn-after-the-card-changes-2026-11-15) were
stored once through the model and copied back before each draw; one message a draw in a new
chat, every card approved.

| Message | Draws | Forget calls | Replies claiming a delete | True note ending the reply | Rows asked to delete left stored |
| --- | --- | --- | --- | --- | --- |
| `Forget everything, my card stays.` | 4 | 0 | 2, and 2 claiming a fresh start or a cleared context | 4: 2 `UNFORGOTTEN_CLAIM_NOTE`, 2 `UNCALLED_FORGET_NOTE` | 12 |
| `Uită tot în afară de card.` | 4 | 0 | 4 | 4: 3 `UNFORGOTTEN_CLAIM_NOTE`, 1 `UNCALLED_FORGET_NOTE`, in Romanian | 12 |

Both messages keep their premise. The card stayed stored in every draw. The turn's request held
the card row alone in each of the 8 draws, after the judge request that held all four. One English
and one Romanian reply also ended with `UNKEPT_CLAIM_NOTE`, after `remains stored` and `Am
reținut.`. Logs `a.jsonl`, `b.jsonl` and `up.txt` and the scripts in
`~/.cache/cortex-run/2026-11-24/f4/stack/`; the Romanian sentences are translated in
`~/.cache/cortex-run/2026-11-24/f4/translations.md`.

## The later clauses read, 2026-11-25

The rule built (`_kept_later` in `forget_permit.py`): for a message that is no forget of
everything the card reads, the clauses after the first one holding a forget verb, or after the
first clause of a message with none, are read as the runs after a value are, and a stored row a
run names in a role no reader reads is kept. Rows are named over the store, as for a forget of
everything, not only from the rows the call matches. Replayed over the family (3,864 cases over
925 messages), the generator of the forget slots (71,332 cases, with the test literals), the
mixed messages (6,156), the a1 word pairs (12,768), the valued cases (4,104) and the negated
messages (8,376), the tree before the change against the tree after it:

| Case set | Keep rows listed before | After | Rows newly listed | Rows asked to delete newly kept |
| --- | --- | --- | --- | --- |
| family, a clause mark before the kept row | 90 | 0 | 0 | 0 |
| family, no clause mark | 222 | 222 | 0 | 0 |
| generator, mixed, pairs, valued, negated | 0 | 0 | 0 | 0 |

The 90 rows are all of the heads with no forget verb: `Wipe everything, the card stays.`,
`Wipe everything, leave the card.`, `Vide tout, la carte reste.` and `Todo fuera, la tarjeta se
queda.`. The 222 with no clause mark are 96 of a head with no forget verb, 66 of a read head and
60 of a word for all left unread, as `Forget everything the card stays.` and `Vergiss alles bis
auf die Karte.`. The generator keeps 104 more rows in 19 test literals that mark no row as asked
to keep or delete: stored row texts, replies and requests to remember, and `Forget the card
4242, the card and the 4242 stay.`, whose card rows the message asks to keep. One test message of the call word
refusal, `Merk dir, dass Rex weg muss.`, now keeps the row its forget call names: the cost of
the rule is that row, against the 24 rows asked to delete in 7 test literals of the rule read
from the rows the call lists alone.

Scripts: `replay.sh`, `cmp.py` and `ecount2.py` in `~/.cache/cortex-run/2026-11-25/f2/`.
