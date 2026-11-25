# Readings: a possessive subject read as a stated fact

What two wider readings of `asks_kept_fact_other` (`fact_request.py`) would cost: each also reads a
fact with a possessive subject and no copula as a stated fact, so `forget_unrequested`
(`forget_unrequested.py`) would refuse the forget tool on it. Counted on 2026-11-25 before any build;
neither shape is in the tree. The losses they target, an old row deleted by an unasked forget call
beside a request to remember, are in
[forget-refusal-stated-fact.md](forget-refusal-stated-fact.md#three-forms-with-no-copula-and-an-older-row-stored-2026-11-25).
The task is
[task 1331](../refinements/tasks/1331-a-request-to-remember-a-fact-with-no-copula-keeps-the-forget-tool-beside-an-older-row.md).

## The two shapes

- **A.** After a request to remember in French, German, Spanish or Romanian, the fact clause opens
  with a first person possessive and one word (`mon`, `ma`, `mes`, `notre`, `nos`, `mein`, `meine`,
  `unser`, `unsere`, `mi`, `mis`, `nuestro` and its forms), or in Romanian one word and then `meu`,
  `mea`, `mei`, `mele`, `nostru`, `noastră` or `noștri`. Two to five more words follow in any
  order, with no second clause and no obligation of the assistant. It holds no verb list.
- **B.** A, where one of the words after the subject starts with a capital letter or holds a digit,
  so that the value is a name or a number.

A reads `Merk dir, dass mein Hund Bello heißt.` and `Ține minte că sora mea vine mâine.`; B reads
the first only. Neither reads the five action forms of
[task 1171](../refinements/tasks/1171-a-request-to-remember-an-action-stated-after-que-dass-or-ca-refuses-the-forget-tool.md),
since each opens with a verb or a pronoun.

## The cost over requests to forget

The rule, written before the count: a shape is built only if it newly refuses at most half of each
family below, a seeded draw on it deletes no old row, and the replay keeps no string the tree
refuses. Each message asks to delete one row, so each message a shape newly refuses keeps one row
the person asked to delete.

- **Family 1**, 239 messages: a request to remember with a possessive subject and a predicate that
  asks for the row to go without a forget verb, ten per language (`weg muss`, `doit partir`, `va a
  la basura`, `a expirat` and others), with the card and phone subjects of the forget generator,
  three remember openers per language, and `Merk dir, dass mein Code weg muss.`.
- **Family 2**, 238 messages: family 1 with the row's value after the subject noun, as in `Merk
  dir, dass meine Karte 4242 weg muss.`. Written after B was counted on family 1.

| Messages | Count | The tree refuses | A newly refuses | B newly refuses |
| --- | --- | --- | --- | --- |
| Family 1 | 239 | 40 | 147 | 10 |
| Family 2 | 238 | 40 | 150 | 150 |
| The forget generator | 42,356 | 0 | 0 | 0 |

The 40 messages the tree refuses state the predicate with a copula (`abgelaufen ist`, `est
périmée`). B's 10 in family 1 are the German predicates holding a noun (`in den Müll gehört`, `in
den Müll kann`, `gehört in den Müll`). No message of the forget generator changed, since none opens
with a request to remember.

**Result: neither shape is built.** A newly refuses more than half of both families, and B more
than half of family 2, where a number is enough for B to read the message. Set against them are
the losses of the stated fact readings: 1 of 16 Bello draws and 2 of 16 sora draws lost both
values, each after an approved card. A refused forget costs the person the forget on every such
message, with no card.

## The replay

74,409 strings: 16,161 string literals of the brain's tests, 16,018 backticked texts of `docs/` and
42,230 messages of the forget generator. The tree refuses 1,079. A newly refuses 10 and B 6, and
neither newly keeps a string the tree refuses. B's six are the Bello message with and without
`Merci.`, `Merk dir, dass mein Hund Rex heißt.`, `Amintește-ți că sora mea se numește Ana.`,
`Rappelle-toi que ma sœur s'appelle Claire.` and `Retiens que mon train part à 8 h.`. A adds the two
sora messages of the readings, `Merk dir, dass mein Code weg muss.` and `Merk dir, dass meine
Dateien in /srv liegen.`.

## What the losing calls named

In each of the six draws of the two readings that deleted an old row unasked, a call named a word
the message does not hold: `Rex`, `sora mea vine vineri`, `sora ta vine vineri`, `mon vélo est
rouge`, `rouge` and `carnívoro`. Every other call of the 2026-11-25 rows named only words of the
message (`Bello`, `Mein Hund heißt Bello.`, `cita a las 9`), except `Sora utilizatorului vine
mâine.`, which matched no row.

Rules in `notes.md`; scripts `famgen.py`, `famgen2.py`, `famcost.py`, `refq.py`, `collect.py` and
`refuse.py`; logs `costA.log`, `costB.log`, `cost2.log` and `replay.log`; in
`~/.cache/cortex-run/2026-11-25/r1/`. The call texts are in `logs/rows-*.jsonl` of
`~/.cache/cortex-run/2026-11-25/s2/`. No draw was taken, since no reader was built.
