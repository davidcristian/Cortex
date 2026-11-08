# A third person statement after a conjunction reads as a request to forget

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-08
**Trigger:** a recorded message, in a draw, a flow record or a test, that states what someone else
forgets or erases after `et`, `mais`, `y`, `pero`, `și` or `dar` in French, Spanish or Romanian.

`asks_not_kept` (`memory_request.py`) reads an imperative to forget or erase at a clause start in
French, German, Spanish and Romanian, and a clause also starts after a conjunction. In French,
Spanish and Romanian the third person singular of `oublier`, `effacer`, `olvidar`, `borrar`, `a uita`
and `a șterge` has the imperative's form, so `Il arrive en retard et oublie ses clés.` returns true
and `memory_withheld` stores nothing of that turn. The reader withholds when unsure, and on
2026-11-08 no recorded string of 13,259 had this form
([readings](../../readings/claim-reader-replays.md#a-forget-in-four-more-languages-and-an-english-keep-idiom-2026-11-08)).

## What to do

When the trigger fires, read whether a subject before the conjunction names someone other than the
person (`il`, `elle`, `mon frère`, `ella`, `el`) and the verb's object is theirs (`ses`, `sus`), and
keep the turn only then. Write near misses that must still withhold first (`Merci et oublie mon
code.`, `Gracias y olvida mi PIN.`), and replay every recorded message through the old and new reader.

## History

- 2026-11-08: filed by the slot that widened the reader to forget imperatives in four more languages.
  Named in [R-1007](1007-a-request-to-forget-in-another-language-answered-without-a-call-is-stored.md).
