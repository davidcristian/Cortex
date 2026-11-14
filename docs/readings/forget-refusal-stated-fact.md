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
`/tmp/claude-1000/-home-david-Files-Git-Cortex/11450320-079c-401d-9f26-43a763a369b6/scratchpad/slot5/`.

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
