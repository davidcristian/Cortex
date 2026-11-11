# The note naming a row kept for a longer value is English only

**Status:** done 2026-11-11
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`inside_note` (`forget_inside.py`) names the rows a `forget_memories` call with no card kept
because each holds the call's text only inside a longer value. Its header `INSIDE_NOTE` is English
under a reply in any language, while `kept_note` on the same turn takes the message's language
(`KEPT_NOTES`). The wording in French, German, Spanish and Romanian is a pick, so it is proposed
here, beside the general case of task 999.

## Proposal

| Language | Header |
| --- | --- |
| en (shipped) | `(Still in memory, since the text a forget call searched for is in each only as part of a longer value:` |
| fr | `(Toujours en mémoire, car le texte qu'un appel d'oubli recherchait n'y figure que dans une valeur plus longue :` |
| de | `(Noch gespeichert, weil der Text, nach dem ein Aufruf zum Vergessen suchte, darin nur als Teil eines längeren Werts steht:` |
| es | `(Todavía en memoria, porque el texto que buscaba una llamada de olvido solo aparece como parte de un valor más largo:` |
| ro | `(Încă în memorie, pentru că textul căutat de o cerere de uitare apare doar ca parte a unei valori mai lungi:` |

## What to do

1. Pick or reword the four headers, then add `INSIDE_NOTES` and a `language` argument as
   `kept_note` has, with a test per language like the kept note's.

## History

- 2026-11-10: filed when the brain started appending the note after a forget whose only match
  holds a longer value.
- 2026-11-11: done. `INSIDE_NOTES` beside `INSIDE_NOTE` and a `language` argument on
  `inside_note`, picked by `message_language` as `kept_note` is. The Spanish and Romanian headers
  gained `en cada uno` and `în fiecare` for the English "in each", and the Romanian one names the
  call `un apel de uitare`, like the call in the other three languages, rather than a request.
