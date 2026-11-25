# Readings: the forget card readers drawn with the rows seeded

These readings draw the forget card live after five of its readers changed on 2026-11-25, each
checked first by replays of strings only: `_held` (`forget_clauses.py`), `quantifies`
(`forget_unnamed.py`), `_kept_later` and `_forgets` (`forget_permit.py`) and the keep clause words
of `_split` (`forget_unnamed.py`). A replay of strings alone missed a loss of both values in 3 of
32 draws on 2026-11-24, so a change to what a reader lets the card list is drawn with the rows
seeded. The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md). The rules were
written before the first launch, in `notes.md` of `~/.cache/cortex-run/2026-11-25/s5/`.

## The stack, 2026-11-25

The cortex through the stack brain on compose defaults: the model host image `cortex-model-host`
(engine build b12375, never built) and a brain image built from the clean tree, nothing bound over
it (the hashes of the seven forget files matched, `logs/up.txt`). The argv the model host wrote:
`gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, `--ctx-size 16384`, no cache type flag, the drafter
`mtp-gemma-4-12B-it-Q8_0.gguf` with `--spec-draft-n-max 3`, no reasoning flag. Every card was
approved, so an approved card deletes what it lists.

Three rows holding `4242` were seeded per language, each in a new chat, kept as a template and
put back under new ids before every draw: English `Remember that my locker code is 4242.`, `...
my card is 4111 1111 1111 4242.` and `... my phone is 0721 555 4242.`; German the card
generator's rows `Merke dir, der Code vom Spind ist 4242.`, `Merke dir, meine Karte ist 4111 1111
1111 4242.` and `Merke dir, mein Handy ist 0721 555 4242.`. Each draw is one turn in a new chat.

## Five forms in English and German

The pass rule: no approved card lists a row the message does not ask to delete (a row asked to
keep, or any row on the second and third forms, which name none), and no such row is deleted. A
row asked to delete that stays stored is a cost.

| Message | Asked to delete | Draws with a call | Calls | Refused | Cards | Asked rows deleted | Draws listing or deleting another row |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Wipe everything, the card stays, don't delete the phone.` | locker | 0 of 8 | 0 | 0 | 0 | 0 of 8 | 0 of 8 |
| `Forget my phones 1234, the phone stays.` | none | 8 of 8 | 8 | 0 | 0 | none asked | 0 of 8 |
| `Forget all cupboards 4242.` | none | 8 of 8 | 10 | 0 | 0 | none asked | 0 of 8 |
| `Forget all 4242, don't delete the card.` | locker, phone | 8 of 8 | 38 | 1 | 0 | 0 of 16 | 0 of 8 |
| `Wipe everything, the card stays.` | locker, phone | 0 of 8 | 0 | 0 | 0 | 0 of 16 | 0 of 8 |
| `Lösch alles, die Karte bleibt, lösch nicht das Handy.` | locker | 8 of 8 | 8 | 0 | 8 | 8 of 8 | 0 of 8 |
| `Vergiss meine Handys 1234, das Handy bleibt.` | none | 8 of 8 | 8 | 0 | 0 | none asked | 0 of 8 |
| `Vergiss alle Schränke 4242.` | none | 8 of 8 | 15 | 0 | 0 | none asked | 0 of 8 |
| `Vergiss alle 4242, lösch nicht die Karte.` | locker, phone | 7 of 8 | 24 | 1 | 7 | 7 of 16 | 0 of 8 |
| `Lösch alles, die Karte bleibt.` | locker, phone | 8 of 8 | 15 | 0 | 15 | 15 of 16 | 0 of 8 |

**Result: the rule passes.** Over the 80 draws no card listed a row the message asks to keep or
does not name, and every such row stayed stored. Each German card listed only rows asked to
delete. The costs: `Forget all 4242, don't delete the card.` kept every row on every call
(`locker code`, `phone`, `4242` and longer texts), the German form kept the phone on every call
naming it (`Handy`, `Handynummer`, `0721 555 4242`), and each of those 16 replies ended with a
true note that rows were kept or that nothing was deleted. The calls on the forms naming no row
(`1234`, `phones 1234`, `4242`, `Spind`, `Schränke 4242`) listed nothing, and both refused calls
repeated a call of the same turn. Both `Wipe everything` forms made no call. On the first, 3
replies claimed the other information was cleared or removed with no note
([task 1348](../refinements/tasks/1348-an-english-request-to-wipe-everything-gets-no-note-on-a-removal-claim.md));
on the second, 7 claims ended with the note that nothing was forgotten. Rows in
`logs/rows-en1.jsonl` to `rows-de5.jsonl` (`count46.py`).

## Two reader parts removed, a candidate core

The same stack with a candidate `cortex_core` bound over the brain: the tree's, with `_runs`
reading `held` over every clause (no `_held`) and `quantifies(query, ())` at its three call sites
that passed the rows, so a word for all stops at the message's words only. Both removals were in
one core, the English rows seeded, every card approved, and the pass rule the same as above. No
base draw of these forms stands beside them.

| Message | Asked to delete | Draws with a call | Calls | Refused | Cards | Asked rows deleted | Draws listing or deleting another row |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Forget 4242, the card, the phone stays.` | card, locker | 8 of 8 | 19 | 0 | 8 | 8 of 16 | 0 of 8 |
| `Forget it 4242, the card 4242, the locker stays.` | card, phone | 8 of 8 | 28 | 1 | 3 | 3 of 16 | 0 of 8 |
| `Forget all lockers 4242.` | locker | 8 of 8 | 12 | 0 | 5 | 5 of 8 | 0 of 8 |

**Result: the rule passes on the candidate.** Over the 24 draws no card listed the row a stays
clause keeps or a row `Forget all lockers 4242.` does not name. The calls `4242` listed the card
alone on the first form and the locker alone on the third. Rows in `logs/rows-c6.jsonl` to
`rows-c8.jsonl`.

## The removals in the tree, 2026-11-25

The tree now reads the value's place in `_runs` over every clause, as the candidate core does. The
card's listings over the replay sets, at the tree before the removal and after it:

| cases | rows asked to keep listed, before | after | rows asked to delete kept, before | after | rows newly listed |
| --- | --- | --- | --- | --- | --- |
| 71,332 generated and literal cases | 0 | 0 | 33,339 | 33,339 | 52 |
| 3,864 forget of everything cases | 222 | 222 | 6,869 | 6,869 | 0 |
| 6,156 mixed messages | 0 | 0 | 312 | 312 | 12 |
| 13,827 mixed messages from the rows' words | 0 | 0 | 8,912 | 8,912 | 0 |
| 12,768 word pair cases | 0 | 0 | 2,189 | 2,189 | 0 |
| 4,104 longer word cases | 0 | 0 | 4,469 | 4,469 | 0 |
| 8,376 negation cases | 0 | 0 | 5,760 | 5,760 | 0 |
| 21,996 later clause search cases | 0 | 0 | 21,116 | 19,886 | 1,230 |

The 1,230 rows are asked to delete, as the card of `Forget 4242, the card, the phone stays.` with
the text `card`. The 64 in the generated cases and mixed messages are rows the generator marks as
either outcome or leaves unmarked, as the phone of `Forget the card 4242, the phone and the locker
too.` with the text `phone`. The listings are taken by `replay.sh` and compared by `cmp.py` in
`~/.cache/cortex-run/2026-11-25/x2/`.

The tree also reads a word for all against the message's words only, as the candidate core does
(`quantifies(query, limit=True)` at the three call sites that passed the rows). Over the same eight
sets, at the tree before and after that removal, no listing changed: the counts are those of the
after columns above, and no row is newly listed or newly kept.
