# A request to forget in another Latin-script language refuses the forget tool

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

`forget_unrequested` (`forget_unrequested.py`) reads English, French, German, Spanish and Romanian
by its word lists, and its letter clause keeps the forget tool only on a letter outside those five
languages (`_READ_LETTERS`)
([readings](../../readings/forget-calls-on-remember-rise.md#the-refusal-in-four-more-languages)).
Italian, Portuguese, Catalan, Dutch, Swedish and Finnish are written mostly in those letters,
Polish often is, and the lists hold none or a few of their forget verbs (`dimentic`, `rimuov`, `esquec`, `apag`, `oblid`, `esborr`,
`vergeet`, `verwijder`). So these requests to forget, each kept by its accented letters before the
letter clause read the four languages, now have the tool refused, which is a privacy loss:

- Italian: `Butta via la nota sulla palestra, è vecchia.`, `Svuota la memoria, è tutto privato.`,
  `Lascia perdere quello che ho detto: è una cosa privata.`
- Portuguese: `Tira o meu número da memória.`, `Limpa a memória sobre a academia.`,
  `Joga fora o que eu disse sobre a minha saúde.`
- Catalan: `Llença el que et vaig dir del gimnàs.`, `Treu la nota del gimnàs, és privada.`
- Dutch: `Wis wat ik zei over België.`, `Wis de notitie over de reünie.`
- Swedish, Finnish and Polish: `Glöm bort det jag sa om gymmet.`,
  `Poista muistista se mitä kerroin terveydestäni.`, `Zapomnij mój stary numer.`

Corrections are refused the same way: `Il numero che ti ho dato è sbagliato: è 4862.`,
`Aggiorna il mio indirizzo: è Via Roma 5.`, `Meu código mudou para 4862.`,
`O meu código já é outro: 4862.` and `He canviat de número: ara és el 555 1234.` Of 37 such
messages in the first four languages, the build before kept the tool on 36 and HEAD keeps it
on 8. `message_language` cannot tell these languages from the five: it reads
`Tira o meu número da memória.` as Romanian and `Llença el que et vaig dir del gimnàs.` as
Spanish.

Reproduction: `forget_unrequested("Wis wat ik zei over België.")` returns `{"forget_memories"}`.

## What to do

1. Write the messages above as tests that keep the tool, beside requests to remember in the same
   languages (`Ricorda che il mio caffè preferito è l'espresso.`) that refuse it.
2. Choose the shape before adding words: a reader that names a message as French, German,
   Spanish or Romanian by words only those languages use, with the letter clause reading the
   four languages' letters only then, or the `a-z` letter clause again. Do not add the four
   languages' words one list at a time.
3. Replay every recorded message and test string through the old and new reader.

## History

- 2026-11-12: filed from the audit of the reader that reads French, German, Spanish and Romanian
  by words, with the Portuguese corrections its build had found.
