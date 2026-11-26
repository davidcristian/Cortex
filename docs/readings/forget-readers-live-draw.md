# Readings: eight forget reader changes drawn with the rows seeded

These readings draw the forget card live after eight of its readers changed on 2026-11-26, each
checked first by replays of strings only: `_head_run` and the word `don` of `don't` in the keep
clause (`forget_permit.py`, `forget_clauses.py`), the word for only (`forget_only.py`), the reach
read before recall (`forget_reach.py`), the Romanian plural (`grows` in `forget_kinds.py`), the
request words every row holds (`_apart` in `forget_keep_named.py`), the head rule after a word for
all (`forget_permit.py`) and `don` left out of `held` (`forget_inside.py`). A change to what a
reader lets the card list is drawn with the rows seeded, since a replay of strings alone missed a
loss of both values in 3 of 32 draws on 2026-11-24. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md). The rules were written before the first
launch, in `notes.md` of `~/.cache/cortex-run/2026-11-26/s3/`.

## The stack, 2026-11-26

The cortex through the stack brain on compose defaults: the model host image `cortex-model-host`
(engine build b12375, never built) and a brain image built from the clean tree, nothing bound
over it (the hashes of eight forget and recall files matched, `logs/up.txt`). The base is the same
image with `cortex_core` and `cortex_memory` of the run's start commit bound over it, the only
brain packages whose sources differ (`logs/swap.txt`). The argv the model host wrote:
`gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, `--ctx-size 16384`, no cache type flag, the drafter
`mtp-gemma-4-12B-it-Q8_0.gguf` with `--spec-draft-n-max 3`, no reasoning flag. Every card was
approved, so an approved card deletes what it lists.

The rows were seeded each from its own new chat, kept as a template and put back under new ids
before every draw: English `Remember that my locker code is 4242.`, `... my card is 4111 1111 1111
4242.` and `... my phone is 0721 555 4242.`; Romanian `Ține minte că codul de la dulap este 4242.`,
`Ține minte că cardul meu este 4111 1111 1111 4242.` and `Ține minte că telefonul meu este 0721
555 4242.`; for the `Don` form the English card and phone and `Remember that Don's phone is 0744
555 4242.`. Each draw is one turn in a new chat.

## One form per change

A row is kept when any reading of a clause keeps it, and a row the message does not name is asked
to keep. **Pass rule:** no row asked to keep is listed or deleted, and no row the message does not
name is deleted. A row asked to delete that stays stored is a cost.

| Change | Message | Asked to delete | Draws with a call | Calls | Refused | Cards | Asked rows deleted | Draws listing or deleting another row |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `_head_run` | `Forget everything the card stays.` | locker, phone | 1 of 8 | 1 | 0 | 0 | 0 of 16 | 0 of 8 |
| `don` in the keep clause | `Forget all 4242, don't delete the card.` | locker, phone | 7 of 8 | 13 | 0 | 13 | 13 of 16 | 0 of 8 |
| the word for only | `Forget 4242, the card too, only the phone.` | phone | 8 of 8 | 26 | 1 | 2 | 0 of 8 | 2 of 8 |
| the reach before recall | `Forget 4242 and Miso, keep the card.` | locker, phone | 8 of 8 | 20 | 0 | 0 | 0 of 16 | 0 of 8 |
| the Romanian plural | `Uită cardurile.` | cardul | 8 of 8 | 10 | 0 | 2 | 2 of 8 | 0 of 8 |
| `_apart` | `Forget what you remembered about my card.` | card | 8 of 8 | 8 | 0 | 8 | 8 of 8 | 0 of 8 |
| the head rule after a word for all | `Forget all of it the card stays.` | locker, phone | 0 of 8 | 0 | 0 | 0 | 0 of 16 | 0 of 8 |
| `don` left out of `held` | `Forget Don, don't remove the card.` | Don's row | 8 of 8 | 8 | 0 | 8 | 8 of 8 | 0 of 8 |

**Result: seven forms pass and the word for only fails.** On seven forms no card listed a row
asked to keep, and every such row stayed stored. `Forget all 4242, don't delete the card.` deleted
the locker and the phone in 13 of 16, where the same form kept every row in all 16 on 2026-11-25
([forget-readers-seeded-draw.md](forget-readers-seeded-draw.md#five-forms-in-english-and-german)).
`Forget Don, don't remove the card.` deleted Don's row alone in all 8 (`Don` 7 times, `Don's
phone` once). `_apart` let the card through in all 8 (`4111 1111 1111 4242` 6 times, `card`
twice). The Romanian plural kept the card on all 8 calls `4111 1111 1111 4242` and deleted it on
`card` and `cardul`. The costs: the reach form kept every row, since its 13 calls naming the value
or a row (`4242`, `locker code`, `phone` and others) returned that the message was not read as
meaning a row and its 7 calls `Miso` matched nothing, and the two forms of everything made one
call (`everything`, which matched nothing) or none. Every reply on a form whose rows were all kept
ended with a true note that nothing was deleted or that the rows are still in memory.

**The failure.** In 2 of 8 draws of `Forget 4242, the card too, only the phone.` the call text
`Remember that my locker code is 4242.` listed the locker, which the reading "only the phone" keeps,
and the approved card deleted it. The same message on the base deleted the card in all 8 and the
locker in none: the word for only removed the card loss. Replayed over the three rows alone, the
call text holding the value beside a word of the row (`locker 4242`, `code is 4242`, `my locker
code is 4242` and the whole request) lists the locker at both trees, on this form and on `Forget
all 4242, only the card.`, while `4242` lists no row other than the card the second form names:
the reader of the word for only named rows by the words of the call's matches alone, so with the
locker the one match, `phone` and `card` named no row it read
([the replay of the fix](forget-form-cells.md#a-word-for-only-beside-a-call-naming-a-row-2026-11-26)).
Rows in `logs/rows-h1.jsonl` to `rows-h8.jsonl` and `rows-o3.jsonl` (`count.py`, `sum.py`).

## The cost of the head rule after a word for all

The head rule reads the words after a word for all in a forget of everything as one more run, so
two plain requests to delete a row now read as keeping it. Each form on the tree and on the base,
8 draws each, the English rows seeded:

| Message | Tree | Draws with a call | Calls | Refused | Cards | Card deleted | Another row deleted |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Delete all of my card details from memory.` | the tree | 8 of 8 | 18 | 0 | 0 | 0 of 8 | 0 of 8 |
| `Delete all of my card details from memory.` | the base | 8 of 8 | 8 | 0 | 8 | 8 of 8 | 0 of 8 |
| `Forget everything on my card please.` | the tree | 8 of 8 | 13 | 0 | 0 | 0 of 8 | 0 of 8 |
| `Forget everything on my card please.` | the base | 8 of 8 | 8 | 0 | 8 | 8 of 8 | 0 of 8 |

**Result: the cost is real.** A person asking to delete the card ends up with it stored in all 16
draws on the tree, against 0 of 16 on the base, where each card listed the card alone. Every call
on the tree but one (`card details`, which matched no row) returned that the message was not read
as meaning a row, and every reply ended with a note that nothing was forgotten or deleted in the
turn. The 8 replies to the first form said the card details were not found; 4 of the 8 to the
second first said the card was cleared, removed or forgotten. The tree now reads a placing word
after the word for all that leads to the one row the clause names as the forget's scope, which
tells these forms from `Forget all of it the card stays.`
([replay](forget-everything-unread-forms.md#heads-of-more-than-one-word-2026-11-26)).
Rows in `logs/rows-k1.jsonl`, `rows-k2.jsonl`, `rows-o1.jsonl` and `rows-o2.jsonl`.
