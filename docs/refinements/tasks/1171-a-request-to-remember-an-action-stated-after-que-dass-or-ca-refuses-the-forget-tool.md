# A request to remember an action stated after que, dass or că refuses the forget tool

**Status:** done 2026-11-14
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`forget_unrequested` (`forget_unrequested.py`) reads the letters of French, German, Spanish and
Romanian only on a request that `asks_kept_fact_other` (`memory_request.py`) reads as one stated
fact, which it takes from `que`, `dass` or `că` after the remember verb
([readings](../../readings/forget-refusal-other-languages.md)).
A fact clause holding an obligation of the assistant or a second `que tu` (`tu dois`, `il faut`,
`debes`, `hay que`, `trebuie`, `să`, `sollst`, `musst`) is read as a request for an action and keeps
the tool. Four forms that ask for an action hold none of those words and are still refused, so the
person needs a second message to have the row forgotten:

- `Recuerda que remuevas mi código.` and `Recuerda que tires mi código.`: a Spanish second person
  subjunctive straight after `que`. The start build `d1620de90` kept both by their accented letter.
- `Souviens-toi que tu jettes mon code.`: `tu` straight after the opening `que`.
- `Merk dir, dass du meinen Code wegwirfst.`: `du` with a finite verb.
- `Tine minte ca vreau sa arunci codul.`: Romanian with no diacritics, where `sa` is also French.

The start build and HEAD refuse the last three as well. Each marker for them is a pronoun or an
ending that also opens a stated fact (`Recuerda que tienes cita a las 9.`, `Souviens-toi que tu es
né en 1990.`, `Souviens-toi que sa voiture est rouge.`), so no closed word separates them.

## What to do

1. Append a note after a call refused as `FORGET_UNREQUESTED` on a message
   `asks_kept_fact_other` reads, when no forget call deleted and `UNFORGOTTEN_CLAIM_NOTE` does not
   show, saying nothing was forgotten and to ask for a forget in a message of its own. It needs a
   `TaintLedger` flag kept by the handoff record. Do not add verbs or verb endings to a reader.
2. Draw rows `a1` to `a5` and `k1` with the next message after each
   ([readings](../../readings/forget-refusal-other-languages.md#an-action-asked-after-que-dass-or-că-rows-and-rule-written-2026-11-13-before-any-draw)),
   by the next rows in [the note's readings](../../readings/forget-unrequested-notes.md#the-draws-2026-11-13).

## History

- 2026-11-12: filed when the four languages' letters became read only on a stated fact with
  no obligation of the assistant, which left these forms refused. No draw was made, since the
  stack was down.
- 2026-11-13: left open. On the stack brain, 6 of 10 draws of the five forms had a forget call
  refused, and 4 of those replied that the request was kept with no note, so the person is not told
  nothing was forgotten. A note built for it showed on every refused setup turn, and its own words
  then kept the tool on the next message, so it was reverted until the forget refusal read the
  last reply without the brain's own notes ([the notes](../../readings/forget-unrequested-notes.md)).
- 2026-11-13: left open. The note was built with `TaintLedger.forget_unrequested` kept by the
  handoff record and drawn after the brain's own notes left the last reply: it closed every refused
  turn with no claim note, and every next message after it had its call refused. On one chain a
  false claim of a delete kept the tool on the next message, so the rule failed and the note was
  reverted ([the draws](../../readings/forget-unrequested-notes.md#the-draws-2026-11-13),
  [task 1180](1180-a-false-claim-of-a-delete-in-the-last-reply-keeps-the-forget-tool-on-the-next-fact.md)).
- 2026-11-14: done, with a different remedy: no note and no new obligation word.
  `asks_kept_fact_other` reads the fact part only when it is stated with a copula, so the five
  forms keep the tool. Asked after a stored code, `Recuerda que remuevas mi código.` deleted the row
  in 3 of 3 draws on the fix and 0 of 3 on the start build. Facts stated with another verb now
  keep the tool, filed as
  [task 1197](1197-a-request-to-remember-a-fact-stated-with-a-verb-that-is-no-copula-keeps-the-forget-tool.md)
  ([readings](../../readings/forget-refusal-stated-fact.md)).
