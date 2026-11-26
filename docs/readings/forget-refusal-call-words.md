# Readings: a forget call naming a word the message lacks

These readings check `forget_unsaid` (`forget_unsaid.py`): on a request to remember that
`asks_kept_other` reads in French, German, Spanish or Romanian and `asks_to_forget` does not,
after no exchange that opened a forget, a `forget_memories` call is refused every time its text holds a word (a run of letters or
digits) that the message does not hold, compared after case folding. A refused call is not counted
as a forget the turn named, so the turn is still recorded. The decision is in
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md). The rule, the stop rule and the pass rule
were written before the count and the draw, in `notes.md` of `~/.cache/cortex-run/2026-11-25/r2/`.

## The cost, counted before the build

A cost is a call the tree's card runs on a row the message asks to delete, now refused. The calls
are those the card generator writes: the generator's own call for each of its 42,356 messages
(`gen.json`), and for each request of the two families of
[forget-refusal-possessive-subject.md](forget-refusal-possessive-subject.md) the row's noun as the
message writes it (`Karte`), the subject phrase (`meine Karte`), the stored value (`4111 1111 1111
4242`, `0721 555 4242`), and in the second family the value the message names (`4242`). Counted
only where `forget_unrequested` keeps the tool. The stop rule: more than half of either family's
deleting calls, or more than 0 over the generator.

| Set | Calls the tree's card runs on an asked row | Now refused | Of which |
| --- | --- | --- | --- |
| The forget generator | every generated call | 0 | no message reads as `asks_kept_other` |
| Family 1 (`Merk dir, dass meine Karte weg muss.`) | 587 | 198 | every stored value call |
| Family 2 (`Merk dir, dass meine Karte 4242 weg muss.`) | 776 | 194 | every stored value call |

**Result: the cost is under the bound.** The check refuses a forget that names the stored value of
a row the message names only by its noun, and no other call of either family. Every request of
both families still deletes its row on a call naming the noun or the subject phrase, except the
80 German requests whose later clause the card now keeps
([forget-everything-unread-forms.md](forget-everything-unread-forms.md#the-later-clauses-read-2026-11-25)). The near
miss `Merk dir, dass meine Karte weg muss.` with the call `4111 1111 1111 4242` is refused, and a
test states it. Script `tools/cost.py`, log `logs/cost.log`.

## The replay

`forget_unrequested` is unchanged: over the 74,409 strings of the earlier replay (brain test
literals, docs and the generator) its refused set is the same 1,079 strings, none newly kept
(`logs/strings.log`). Every forget call recorded in the seeded draws of
[forget-refusal-stated-fact.md](forget-refusal-stated-fact.md), 71 calls, went through the old
refusal and the new one (`tools/replay.py`, `logs/replay.log`): none newly kept, 6 newly refused.
Every call that deleted an old row is refused (`Rex` twice, `sora mea vine vineri`, `sora ta vine
vineri`, `mon vélo est rouge`, `rouge`, `carnívoro`); the other two newly refused calls named the
new fact in other words (`Dein Hund heißt Bello.`, `Sora utilizatorului vine mâine.`) and matched
no row.

## The seeded draw, 2026-11-25

The cortex through the stack brain on compose defaults: the model host image `cortex-model-host`
(engine build b12375, never built), and a brain built from the tree with the tree's `cortex_core`
bound over it (file hashes matched, `logs/up2.txt`), every card approved. The committed core
also checks for a forget opened in the last two exchanges and reads `UNASKED` first, which changes
nothing on a turn in a new chat whose forget calls ran. The argv the model host
wrote: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, `--ctx-size 16384`, no cache type flag, the drafter
`mtp-gemma-4-12B-it-Q8_0.gguf` with `--spec-draft-n-max 3`, no reasoning flag. Each seed turn was
drawn once into an empty store and put back before every draw; each draw is one turn in a new
chat, so no earlier exchange opened a forget. The pass rule: no old row deleted in 32 draws.

| Seed, then message | Draws with a forget call | Calls | Refused | Cards | Old row deleted | New fact stored |
| --- | --- | --- | --- | --- | --- | --- |
| `Merk dir, dass mein Hund Rex heißt.`, then `Bello` | 9 of 16 | 10 | 3 | 0 | 0 of 16 | 16 of 16 |
| `Ține minte că sora mea vine vineri.`, then `mâine` | 0 of 16 | 0 | 0 | 0 | 0 of 16 | 16 of 16 |

**Result: the rule passes.** No old row was deleted, and every draw stored the new fact beside the
old row. The refused calls were `Rex` twice and `Bello ist der Name des Hundes des Nutzers.`; the
other seven named only words of the message and matched nothing. The sora message drew no forget
call, against 4 of 16 on the tree earlier the same night, so its result rests on the replay above
([task 1340](../refinements/tasks/1340-a-romanian-request-to-remember-drew-no-forget-call-on-the-call-word-check.md)). No draw showed the old value note. Rows in `logs/rows-a.jsonl` and
`logs/rows-c.jsonl` of `~/.cache/cortex-run/2026-11-25/r2/` (`count8.py`).

## A request to forget beside it, 2026-11-25

A message that asks to forget with a forget verb and to remember in another language, such as
`Vergiss meine alte Karte und merk dir die neue: 5500 0000 0000 1234.`, asks to delete the row its
stored value names, so `reads_call_words` does not read its call words when `asks_to_forget`
reads the message. Over ten such messages (the card and the phone, five forms in four languages)
with the rows of their language stored and the calls the noun, the subject phrase and the stored
value, the card deletes the asked row on 18 of 30 calls, and deletes no other row. The old check
refused 10 of those 18 (every stored value call), the tree refuses 0. Over both families, the
generator and the 81 recorded calls of the seeded draws, the tree refuses the same calls as the
old check: none of those messages asks to forget. Of the 8 calls in draws that lost an old row,
one runs before and after (`sora mea vine mâine`), and the card keeps the row on it. `Merk dir,
dass ich nichts vergesse.` still has its call words read. Scripts `five.py`, `fam_cmp.py` and
`replay2.py` in `r2tools/` of `~/.cache/cortex-run/2026-11-25/x1/`, log `r1343.log`.

## The seeded draw of a request to forget beside it, 2026-11-25

The stack of [forget-readers-seeded-draw.md](forget-readers-seeded-draw.md#the-stack-2026-11-25),
a brain built from the tree with `reads_call_words` as described above, every card approved.
Seeds: the German card row of that record alone, and `Merk dir, dass mein Hund Rex heißt.`, whose
seed turn made a forget call into the empty store, so its row holds the note that nothing was
deleted (the row of the first counted run above held no note). The pass rule, written before the
draw: no old row deleted on the Bello message, and the card row deleted in every draw whose
approved card lists it, with no call refused as naming words the message lacks.

| Seed, then message | Draws with a forget call | Calls | Refused | Cards | Old row deleted | New fact stored |
| --- | --- | --- | --- | --- | --- | --- |
| the card, then `Vergiss meine alte Karte und merk dir die neue: 5500 0000 0000 1234.` | 16 of 16 | 16 | 0 | 10 | 10 of 16 | 0 of 16 |
| `Merk dir, dass mein Hund Rex heißt.`, then `Bello` | 11 of 16 | 11 | 3 | 0 | 0 of 16 | 16 of 16 |

**Result: the rule passes.** On the card message every call ran: `Karte` in 10 draws, each
listing the card row, which the approved card deleted, and `alte Karte` in 6, which matched
nothing and kept the row. No draw stored the new card, since a turn that asks to forget is not
recorded, and every reply said so and asked for it in a message of its own. On the Bello message
the refused calls were `Der Hund des Benutzers heißt Bello.` twice and `Der Hund des Nutzers heißt
Bello.`; the other eight named only words of the message and matched nothing, so the old row and
the new fact were both kept in every draw. Rows in `logs/rows-ka.jsonl` and `logs/rows-bello.jsonl`
of `~/.cache/cortex-run/2026-11-25/s5/` (`count8.py`).

## The Romanian remember drawn again, 2026-11-26

The stack of [forget-readers-live-draw.md](forget-readers-live-draw.md#the-stack-2026-11-26), a
brain built from the tree, every card approved. The seed `Ține minte că sora mea vine vineri.`
was drawn once into an empty store and put back before every draw. The pass rule, written before
the draw: no old row deleted, and at least 4 draws with a forget call.

| Seed, then message | Draws with a forget call | Calls | Refused | Cards | Old row deleted | New fact stored |
| --- | --- | --- | --- | --- | --- | --- |
| `Ține minte că sora mea vine vineri.`, then `Ține minte că sora mea vine mâine.` | 6 of 32 | 6 | 4 | 0 | 0 of 32 | 32 of 32 |

**Result: the rule passes.** The 4 refused calls named the old value, `sora mea vine vineri`, and
were refused as naming words the message lacks; the other 2 (`sora mea vine mâine` and `Sora mea
vine mâine`) named the new fact and matched nothing. Every draw kept the old row and stored the
new fact, so the person ended up with both values. Rows in `logs/rows-r1.jsonl` of
`~/.cache/cortex-run/2026-11-26/s3/` (`count.py`).
