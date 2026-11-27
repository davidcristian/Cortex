# A request to remember that a value is outdated refuses the forget tool outside English

**Status:** done 2026-11-27
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`forget_unrequested` keeps the forget tool when a word of `RETRACT_WORDS` can retract a stored
fact. English reads `outdated`, `obsolete`, `stale` and `wrong`, so `Remember that the number is
outdated.` keeps it. The French, German, Spanish and Romanian words for the same thing are not in
the list, and `asks_kept_fact_other` reads each message below as a stated fact, so each is refused
on the start build of 2026-11-14 and on HEAD (`forget_unrequested` alone, no model):
`Merk dir, dass die Nummer veraltet ist.`, `Merk dir, dass der Code ungültig ist.`, `Merk dir,
dass der Termin abgesagt ist.`, `Retiens que ce code est périmé.`, `Retiens que mon adresse est
fausse.`, `Recuerda que ese número ya es viejo.`, `Recuerda que el código está caducado.`, `Ține
minte că numărul acela e expirat.` and `Ține minte că parola e invalidă.`.

A new value has the same shape: `Souviens-toi que mon vélo est bleu.`, `Recuerda que soy
vegetariano.`. A rule that keeps the tool on a value of one lowercase word keeps it on both, and
with the old value stored an unasked forget call then deleted the old row
([readings](../../readings/forget-refusal-stated-fact.md#a-new-value-with-the-old-one-already-stored)).

## What to do

1. The cost side is drawn: with the old value stored, the German and Spanish messages each had a
   refused call in 3 of 8 draws and no note, so the person kept the old code without being told
   ([readings](../../readings/forget-refusal-stated-fact.md#a-value-said-to-be-outdated-the-old-value-stored-2026-11-26)).
2. That cost is real. Count, over the 7 draws with a refused call, whether a note shown when a
   refused forget call names a value a stored row holds would reach each of them: it keeps the
   refusal and tells the person. Write the note to be true on every turn it reaches, with its
   tests first. `forget_unrequested` is not widened and no word list of words that mean outdated
   is added.
3. Draw the note with the old value stored, and decline with the count if it cannot reach the
   draws. Replayed through the note's code, the 7 recorded draws with a refused call all reach it:
   each call named `5528` or `Code 5528`, which the seeded row holds whole. **Pass rule**, written
   before the draw: the German and Spanish messages, 8 draws each, the old value seeded. The note
   passes when every draw with a refused call naming `5528` shows it, no other draw shows it, no
   old row is deleted and the new message is stored in every draw. A refused call without the note,
   or the note on a draw without one, fails it. No refused call in 16 draws is a null result: the
   replay stands and this step stays open.

## History

- 2026-11-14: filed by the audit of the night's forget refusal changes.
- 2026-11-24: a rule keeping the tool on a stated value of one lowercase word kept the nine
  messages above, and was drawn on the card with the old value stored: on a new value of the same
  shape it deleted the old row in 3 of 32 draws, against 0 of 32 with the refusal, so the refusal
  stays and the cost side stays open
  ([readings](../../readings/forget-refusal-stated-fact.md#a-value-of-one-lowercase-word-2026-11-24)).
- 2026-11-26: step 1 drawn with the old value seeded, 8 draws per message, every card approved:
  `Retiens que ce code est périmé.` refused a call in 1 draw, `Merk dir, dass der Code ungültig
  ist.` and `Recuerda que el código está caducado.` in 3 each; no old row deleted, the new message
  stored in all 24, no note shown. By the rule written before the draw the cost is real on the
  German and Spanish messages, and step 2 is next.
- 2026-11-26: meets the bar of the freeze of the forget message readers ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7): it rests on seeded live draws of messages a person types, 7 of 24 with a refused call, and its remedy is a note shown on a refused call; the fallback that kept the tool on these messages widened a reader and is removed from step 2.
- 2026-11-27: done. A refused forget call naming a whole value a stored row still holds now ends
  the reply with `REFUSED_HELD_NOTE` (`forget_refused_held.py`) in the message's language; the
  refusal and `forget_unrequested` are unchanged. The note reached 7 of the 7 recorded draws in a
  replay and, drawn live with the old value seeded, all 3 of 16 draws with a refused call, with no
  note elsewhere and no old row deleted
  ([readings](../../readings/forget-refused-held-note.md)). A call the cortex made before a
  handoff gives no note, since the handoff record does not keep the call texts
  ([task 1374](1374-a-refused-forget-call-made-before-a-handoff-gives-no-refused-held-note.md)), and
  `Retiens que ce code est périmé.` gets the English note, since `message_language` reads it as
  English ([task 1375](1375-a-short-french-request-to-remember-gets-its-notes-in-english.md)).
