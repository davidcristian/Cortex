# Readings: the note on a refused forget call naming a stored value

These readings count `REFUSED_HELD_NOTE` (`forget_refused_held.py`): a reply on a turn whose
forget call was refused as unasked, as unrequested or for words a request to remember lacks ends
with it when a stored row still holds, whole, a value the call named. The refusal is unchanged. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md); the cost the note answers is drawn in
[forget-refusal-stated-fact.md](forget-refusal-stated-fact.md#a-value-said-to-be-outdated-the-old-value-stored-2026-11-26).
The rules were written before the first launch, in `notes.md` of `~/.cache/cortex-run/2026-11-27/c3/`.

## The recorded draws replayed, 2026-11-27

The 7 draws of 2026-11-26 with a refused call were replayed through `hold_stored_values` and
`limit_notes` of the tree: the seeded row, each draw's message, reply and call texts, nothing else
set (`reach.py` and `reach.log` in the run directory). Every call named `5528` (6 draws) or
`Code 5528` (1 draw), which the seeded row holds whole, so **the note reaches 7 of 7**. The French
message `Retiens que ce code est périmé.` gets the French note: its `est` and `ce` tie French with
Romanian, and its `é` breaks the tie ([note-language-letter-tie.md](note-language-letter-tie.md)).

## The live draw, 2026-11-27

The cortex through the stack brain on compose defaults: the model host image `cortex-model-host`
(engine build b12375, never built) and a brain image built from the working tree, HEAD with the
note, nothing bound over it (the hashes of five forget and turn files matched, `logs/up.txt`). The
argv the model host wrote: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, `--ctx-size 16384`, no cache type
flag, the drafter `mtp-gemma-4-12B-it-Q8_0.gguf` with `--spec-draft-n-max 3`, no reasoning flag.
Each old value was seeded from its own new chat, kept as a template and put back under new ids
before every draw; each draw is one turn in a new chat, every card approved. Counted by
`count_c3.py` in the run directory (`logs/count-q1.txt`, `logs/count-q2.txt`).

| Seed, then message | Draws with a forget call | Refused, naming `5528` | Note shown | Note without a refused call | Old row deleted | New message stored |
| --- | --- | --- | --- | --- | --- | --- |
| `Merk dir, dass mein Code 5528 ist.`, then `Merk dir, dass der Code ungültig ist.` | 1 of 8 | 1 | 1 | 0 | 0 of 8 | 8 of 8 |
| `Recuerda que mi código es 5528.`, then `Recuerda que el código está caducado.` | 2 of 8 | 2 | 2 | 0 | 0 of 8 | 8 of 8 |

**Result: the note passes the rule written before the draw.** Every call was refused and named
`5528`, each of the 3 replies after one ended with the note in the message's language, no other
reply had a note of any kind, no card was shown and no old row was deleted. Refused calls were
fewer than on 2026-11-26 (3 of 16 against 6 of 16), so the reach of the note rests on 3 live
draws and the 7 replayed ones.
