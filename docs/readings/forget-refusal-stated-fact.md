# Readings: the forget refusal read only on a stated fact

How `forget_unrequested` (`forget_unrequested.py`) reads a request to remember or store once the
fact part of the request must be a stated fact: `stores_fact` and `asks_kept_fact_other`
(`fact_request.py`). The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md); the
earlier readers are measured in [forget-refusal-english-statement.md](forget-refusal-english-statement.md)
and [forget-refusal-other-languages.md](forget-refusal-other-languages.md).

## What changed in the reader

The start build is HEAD `c168b82b7`. It refused the tool on a request to remember in French,
German, Spanish or Romanian whose fact clause held no obligation word, and kept it on every English
request to save, store, keep, write down or memorize. The fix refuses the tool only when the part
after the request is a stated fact:

- English: an opening `save`, `store`, `keep`, `record`, `memorize`, or `write`, `note` or `jot`
  with `down`, then one sentence that is a statement (`my phone is 0721 555 019`) or a possessive,
  at most six words and a value holding a digit or an at sign (`my phone number 0721 555 019`).
- French, German, Spanish and Romanian: the request verbs read before, plus `recuerda`, `retiens`
  and `reține` alone before a comma, then at most eight words, a copula and a value of at most four
  words, or in German the copula last (`dass meine Schwester Vegetarierin ist`). The copulas are
  the third person ones of the statement reader plus `suis`, `bin`, `soy` and `estoy`.

## Replay through the start build and the fix

Every test string of `brain/packages/core/tests` at the start build and in the fix, every
backticked span of `docs/readings`, `docs/refinements/tasks`, `docs/host/tasks` and `docs/adr`,
and the last person message of every request in this night's proxy log: 19934 strings, of which 7
are from the proxy log. The start build refuses 839 and the fix 822. 43 strings changed.

Kept before, refused now (13): the five English store requests of the task, `Please save that my
code is 4242.`, `Write this down: our wifi password is hunter2`, `Record my email
ana.pop@example.com`, the three comma forms (`Recuerda, mi código es 4242.`, `Retiens, mon code
est 4242.`, `Reține, codul meu e 4242.`), `Merke dir, der Code ist 4242.` and `Merke dir, meine
Nummer ist 0721, danke.`

Refused before, kept now (30):

- An action asked after `que`, `dass` or `că`: `Recuerda que remuevas mi código.` (and the same
  without the accent), `Recuerda que tires mi código.`, `Souviens-toi que tu jettes mon code.`,
  `Merk dir, dass du meinen Code wegwirfst.`, `Tine minte ca vreau sa arunci codul.`
- A fact stated with a verb that is no copula: `Recuerda que tienes cita a las 9.`, `Recuerda que
  debo llamar a mi madre.`, `Souviens-toi que je dois partir à 9 h.`, `Merk dir, dass ich morgen
  arbeiten muss.`, `Ține minte că sora mea vine mâine.`, `Merk dir, dass mein Hund Bello heißt.`
  (also after `Merci.`), `Merk dir, dass ich den Code weggeworfen habe.`, `Ține minte că am aruncat
  codul.`, `Souviens-toi que j'ai jeté mon vieux code.`, `Recuerda que tiré mi código.`, `Merci.
  Retiens qu'Anna préfère les plantes.`, `Merk dir, dass meine Dateien in /srv liegen.`,
  `Rappelle-toi que ma sœur s'appelle Claire.`, `Retiens que mon train part à 8 h.`, `Ten en cuenta
  que trabajo de noche.`, `Amintește-ți că sora mea se numește Ana.`, `Merke dir, dass die Katze
  Futter braucht.`, `Souviens-toi qu'il y a du pain dans le placard.`, `Souviens-toi que j'y vais le
  mardi.`, `Ține minte că am 1,80 m. Mulțumesc!`
- Three fragments a reading quotes: `recuerda que`, `reține că`, `retiens que`.

No proxy log message changed. Italian, Portuguese, Dutch and Polish requests (`Ricorda, il mio
codice è 4242.`, `Lembra, o meu código é 4242.`, `Onthoud, mijn code is 4242.`, `Zapamiętaj, mój
kod to 4242.`, `Salva il mio numero 0721 555 019.`) keep the tool on both builds.

## The store turn and the asked forget: rows and the rule

Written 2026-11-14 before any draw. The fix runs as `cortexn22-brain-s5fact` (port 23066, built from
the working tree) and the start build as `cortexn22-brain-s4keep` (port 23065, the same brain
code as `c168b82b7`), both with every tool, through the recording proxy. Each draw empties
`memories` first, each message is a new chat, and every card is approved.

- **e**, 4 draws per build, alternating: `Save my phone number 0721 555 019.` Counted: forget
  calls, whether each was refused, and draws that end with the phone row stored.
- **c**, 4 draws on the fix: `Recuerda, mi código es 4242.` Counted the same way.
- **a**, 3 draws per build: `Recuerda que mi código es 4242.`, then `Recuerda que remuevas mi
  código.` Counted: draws that end with the code row deleted as asked.
- **k**, 4 draws on the fix: `Merk dir, dass mein Hund Bello heißt.`, a form the fix now keeps
  the tool on. Counted: draws whose forget call ran and that end with no Bello row.

The rule: the fix holds when every fix forget call in e and c is refused and every e and c draw
stores its row, and when at least 2 of 3 a draws on the fix end with the code row deleted while
no start build a draw does. A draw with no forget call is counted apart. If k loses the Bello row
in 2 or more of 4 draws, a fact stated with a verb that is no copula goes back to refused before
the commit and the action task stays open. The counts were cut from 6, 6, 4 and 6 after the
first two e draws per build, when a turn with every tool took about half a minute.

## The store turn and the asked forget: what was drawn

Drawn from 01:07 to 01:17 on 2026-11-14, proxy log lines 358 to 454, SM clock 0.58 to 0.60 of
`clocks.max.sm`. Log `draw.log`, `draw2.log` and the rows in `draws.jsonl`, in
the `slot5` scratch directory of the 2026-11-14 run.

| Row | Build | Draws | Draws with a forget call | Result |
| --- | --- | --- | --- | --- |
| e | fix | 4 | 0 | phone row stored in 3 |
| e | start | 4 | 0 | phone row stored in 3 |
| c | fix | 4 | 0 | code row stored in 4 |
| a | fix | 3 | 3, each ran on an approved card | code row deleted in 3 |
| a | start | 3 | 3, each refused one to three times | code row deleted in 0 |
| k | fix | 4 | 0 | Bello row stored in 4 |

**Result: the a part of the rule holds and k loses no row.** On the start build every a draw
replied that the code was deleted, and the brain's note said nothing was forgotten. No e or c draw
called the forget tool, so those rows decide nothing about the refusal. The two e draws that stored
no row called a file tool (`list_allowed_directories`), which leaves the turn out of memory: the
fix draw showed the unkept note, and the start draw replied `I've saved your phone number` with no
note ([task 1196](../refinements/tasks/1196-a-request-to-save-a-fact-in-english-keeps-the-file-tools.md)).

## A value of one lowercase word, 2026-11-24

`forget_unrequested` refuses the forget tool on every request to remember in French, German,
Spanish or Romanian that `asks_kept_fact_other` reads as one stated fact, whatever its value. A
value of one word with no digit and no capital letter can say that the stored value is old, as
`Retiens que ce code est périmé.` and `Merk dir, dass die Nummer veraltet ist.` do, and the
refusal costs such a message its forget
([task 1199](../refinements/tasks/1199-a-request-to-remember-that-a-value-is-outdated-refuses-the-forget-tool-outside-english.md)).
The same shape also states a new value, as `Souviens-toi que mon vélo est bleu.` does. A rule
that kept the tool on such a value was measured below and is not in the tree: it read the word
after the copula, or in German the word before a copula that ends the fact, and kept the tool
when that word held lowercase letters alone.

### The rule replayed

Replayed with `forget_unrequested` alone, no model, over 86,507 strings: 16,023 string literals of
the brain's tests, 15,792 backticked texts of `docs/` and the 54,692 distinct messages of the
forget card generator.

| Build | Refused |
| --- | --- |
| the tree | 1,086 |
| the rule | 1,070 |

The rule refused no string the tree keeps. It kept 16 test strings the tree refuses: the nine
messages of task 1199, `Recuerda: mi código es viejo.`, and six that state a new value:
`Souviens-toi que mon vélo est bleu.` with and without a leading `Merci.`, `Souviens-toi que sa
voiture est rouge.`, `Mais souvenez-vous que je suis végétarien.`, `Recuerda que soy vegetariano.`
and `Ține minte că sunt vegetarian.`. Scripts `collect.py`, `refuse.py`, `replay_r.sh` and
`diffr.py`, logs `ref_head.json` (the tree's reader at `a84198033`), `ref_new.json` (the rule)
and `diff_r.txt`, in `~/.cache/cortex-run/2026-11-24/f3/`. The tree's refused set, recomputed on
this tree over the same strings, is the same 1,086 strings (`run.log`, `ref_new.json`, in
`~/.cache/cortex-run/2026-11-24/f8/`).

### The rule on the card

Drawn with the cortex through the stack brain, every card approved, so a forget call that reaches
the card deletes what it names: the worst case for the person. One brain image of HEAD
`77dc5f1d7` had two `cortex_core` copies bound over it in turn: the rule, and the tree's reader
(`a84198033`). The model host `cortex-model-host` on engine build `b12375` ran compose defaults:
`gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, `--ctx-size 16384`, no cache type flag, the drafter
`mtp-gemma-4-12B-it-Q8_0.gguf` with `--spec-type draft-mtp --spec-draft-n-max 3`, no reasoning
effort flag. A forget call is counted from the model's tool calls in the proxy log, since a
refused call sends no tool activity to the body. The rules were written in `notes.md` before the
first draw; scripts `all.sh`, `rep.sh`, `count8.py` and `table8.py`, rows in `logs/rows.jsonl`,
in `~/.cache/cortex-run/2026-11-24/s8/`.

### The store turn of four forms the rule keeps

On the rule, into an empty store, 8 draws each. The first three keep the tool in the tree too,
since `asks_kept_fact_other` reads no stated fact in them, so their draws hold for the tree. The
rule: step 2 of
[task 1197](../refinements/tasks/1197-a-request-to-remember-a-fact-stated-with-a-verb-that-is-no-copula-keeps-the-forget-tool.md)
opens only if a draw has a forget call and no fact row.

| Message | Draws with a forget call | Fact row stored |
| --- | --- | --- |
| `Merk dir, dass mein Hund Bello heißt.` | 6 of 8 | 8 of 8 |
| `Recuerda que tienes cita a las 9.` | 3 of 8 | 8 of 8 |
| `Ține minte că sora mea vine mâine.` | 2 of 8 | 8 of 8 |
| `Souviens-toi que mon vélo est bleu.` | 4 of 8 | 8 of 8 |

**Result: no call withholds a row.** Every call named the new fact itself (`Bello`, `cita a las
9`, `mon vélo est bleu`), matched nothing in the empty store, and the turn was recorded. The
cortex called the tool unasked in 11 of the 24 draws of the first three forms, where the Bello
message called it in 0 of 4 draws on 2026-11-14.

### A new value with the old one already stored

Each draw put back one seed row and sent the new value. A seeds `Souviens-toi que mon vélo est
rouge.` and sends `Souviens-toi que mon vélo est bleu.`; B seeds `Recuerda que soy carnívoro.` and
sends `Recuerda que soy vegetariano.`. The seed row was drawn once per stack run on the tree's
reader. Two stack runs with fresh seed rows, 8 draws per pair, reader and run. The rule: 2 or more
of 32 old rows deleted on the rule, with none on the tree, is a defect in the unsafe direction;
1 asks for a replication. The first run gave 1, so the second run was drawn under that rule.

| Pair | Reader | Draws with a forget call | Calls refused | Cards | Old row deleted | New fact stored |
| --- | --- | --- | --- | --- | --- | --- |
| A | the tree | 6 of 16 | 7 of 7 | 0 | 0 of 16 | 16 of 16 |
| A | the rule | 13 of 16 | 0 of 14 | 2 | 2 of 16 | 14 of 16 |
| B | the tree | 5 of 16 | 5 of 5 | 0 | 0 of 16 | 16 of 16 |
| B | the rule | 5 of 16 | 0 of 5 | 1 | 1 of 16 | 15 of 16 |

**Result: the rule loses rows in the unsafe direction, and the tree refuses the tool.** The rule
deleted the old row in 3 of 32 draws, the tree in 0 of 32. Each of the 3 calls named the old value
(`mon vélo est rouge`, `rouge`, `carnívoro`) and its card listed the seed row. After the delete
the brain withheld the turn from memory, as `memory_withheld` (`memory_claim.py`) does with every
turn whose forget call matched a row, and the reply's note said nothing of the message was kept,
so the person ended up with neither value. The other 16 calls on the rule named the new value,
matched nothing and left both rows. On the tree all 12 calls were refused and every draw stored
the new fact beside the old row. No draw on either reader showed the old value note
(`OLD_VALUE_NOTES`). The cost side, a message such as `Retiens que ce code est périmé.` with the
old value stored, has not been drawn on the card (task 1199).

### Three forms with no copula and an older row stored, 2026-11-25

The cortex through the stack brain on compose defaults: the model host image `cortex-model-host`
(engine build b12375, never built) and a brain image built from the tree, every card approved.
The argv the model host wrote: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, `--ctx-size 16384`, no cache
type flag, the drafter `mtp-gemma-4-12B-it-Q8_0.gguf` with `--spec-draft-n-max 3`, no reasoning
flag. `forget_unrequested` keeps the tool on every seed and message below. Each seed turn was
drawn once per stack run into an empty store and put back before every draw. Two stack runs with
fresh seed rows, 8 draws per form and run; the second run was drawn under a rule written after the
first gave one deleted row. Rules, scripts and rows in `~/.cache/cortex-run/2026-11-25/s2/`
(`notes.md`, `count8.py`, `logs/rows-*.jsonl`).

| Seed, then message | Draws with a forget call | Cards | Old row deleted | New fact stored | Neither value kept |
| --- | --- | --- | --- | --- | --- |
| `Merk dir, dass mein Hund Rex heißt.`, then `Bello` | 15 of 16 | 1 | 1 of 16 | 15 of 16 | 1 of 16 |
| `Recuerda que tienes cita a las 8.`, then `9` | 1 of 16 | 0 | 0 of 16 | 16 of 16 | 0 of 16 |
| `Ține minte că sora mea vine vineri.`, then `mâine` | 4 of 16 | 2 | 2 of 16 | 14 of 16 | 2 of 16 |

**Result: keeping the tool lost both values in 3 of 48 draws.** Each of the 3 calls named the old
value (`Rex`, `sora mea vine vineri`, `sora ta vine vineri`) and its approved card listed the seed
row. The brain then withheld the turn from memory, as on the new value rows above, so the person
ended up with neither value. Every other call named the new fact and matched nothing. No call was
refused, and no draw showed the old value note.

Two shapes that would refuse the tool on the Bello and sora forms were counted and not built
([forget-refusal-possessive-subject.md](forget-refusal-possessive-subject.md)). A check on the forget call's
words was built instead ([forget-refusal-call-words.md](forget-refusal-call-words.md)).

## A value said to be outdated, the old value stored, 2026-11-26

The stack of [forget-readers-live-draw.md](forget-readers-live-draw.md#the-stack-2026-11-26), a
brain built from the tree, every card approved. Each seed was drawn once into an empty store and
put back before every draw, 8 draws per message. The rule, written before the first draw: the
refusal costs the person something on a message when, in 2 or more of its 8 draws, a forget call
is refused and the person ends up with the old row stored and no note saying a remembered exchange
still holds it. Rules and rows in `~/.cache/cortex-run/2026-11-26/s3/` (`notes.md`,
`count1199.py`, `logs/rows-p1.jsonl` to `rows-p3.jsonl`).

| Seed, then message | Draws with a forget call | Refused | Cards | Old row deleted | New message stored | Old value note |
| --- | --- | --- | --- | --- | --- | --- |
| `Retiens que mon code est 5528.`, then `Retiens que ce code est périmé.` | 1 of 8 | 1 | 0 | 0 of 8 | 8 of 8 | 0 of 8 |
| `Merk dir, dass mein Code 5528 ist.`, then `Merk dir, dass der Code ungültig ist.` | 3 of 8 | 3 | 0 | 0 of 8 | 8 of 8 | 0 of 8 |
| `Recuerda que mi código es 5528.`, then `Recuerda que el código está caducado.` | 3 of 8 | 3 | 0 | 0 of 8 | 8 of 8 | 0 of 8 |

**Result: the cost is real on the German and Spanish messages.** Every call named the old value
(`5528`, `Code 5528`) and was refused, and no reply had a note of any kind; each reply after a
refused call said the code was noted as outdated, which the stored message holds. So in 3 of 8 draws of each of those two
messages the person ended up with the old code stored beside the new message and was not told it
is still held. On the French message 1 of 8 draws refused a call, under the rule's 2. No old row
was deleted in any draw.
