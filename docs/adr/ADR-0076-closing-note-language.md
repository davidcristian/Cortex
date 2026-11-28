# ADR-0076: A closing note is written in the language of the person's message

**Status:** Accepted (2026-11-08)

## Context

`limit_notes` (`brain/packages/core/src/cortex_core/closing_notes.py`) closes a reply with a fixed
note when a typed check of the turn finds something the reply did not say or said wrongly, such as
the time a reminder was stored at. Every note was an English sentence, so a person who wrote in
French, German, Spanish or Romanian read a French reply ending in English
([readings](../readings/closing-note-language.md)). The brain does not know the language of the
reply: the model writes it, and nothing types it.

Three ways to write the note in the right language were compared.

- **(a) The language of the person's message**, read with a small word list per language. The
  brain has the message (`query`), and the request readers in `memory_request.py` already read the
  same four languages. Over the 749 recorded replies of the last two nights, the pick named a
  language other than the reply's for none, and fell back to English under 9 replies in another
  language.
- **(b) One English note the model restates.** The note is then model text. Five recorded draws
  that restated a scheduling result's note in the reply's language all changed "Ask to make it one
  time" into a promise to adjust it, and the Romanian one has two words that are not Romanian. A
  note the brain appends after a typed check is the form that has held, night after night, where a
  note the model reads did not. Restating after the reply would also cost a second model call per
  noted turn.
- **(c) Both English and the detected language.** Always readable, but every noted reply doubles
  its note, and the second copy adds nothing when the pick is right.

## Decision

1. **A closing note is written in the language `message_language(query)` picks**
   (`cortex_core/note_language.py`): the one of English, French, German, Spanish and Romanian
   whose word list the message matches most, plus the Spanish marks ¿ and ¡. A word two of the
   languages share does not count ("la", "de", "que"). Letters only break a tie: of the languages
   tied for the most words, the one whose own letters (`_LETTERS`: é, ä, ñ, ș and the like) the
   message holds most is picked, so `Retiens que ce code est périmé.` (French `est`, Romanian
   `ce`) is French. Letters also decide one case without a tie: when the one language that
   scores scores a single word that another language also writes (`_ALSO_WRITTEN`, French for the
   Romanian `ce`), the one of the two whose letters the message holds most is picked, and a letter
   tie keeps the language that scored, so `Retiens bien ce code périmé.` is French and `Ce faci?`
   stays Romanian. Letters decide nothing else, because a name such as Jürgen or María has them
   in a message of any language, and a letter of a language outside the tie counts for none
   ([readings](../readings/note-language-letter-tie.md)). A word in capitals (`EU`, `EST`) and
   a capitalized word beside another inside a sentence (`Las Vegas`) are names and do not count,
   except a word German capitalizes anywhere (`Uhr`, `Morgen`, the polite `Sie`), so
   `Termin Montag 9 Uhr` stays German. The `am` of a clock figure such as `9am` counts as English.
   A message with no lowercase letter also counts its words of four letters or more when two of
   them are in one language's list, so `RAPPELLE-MOI DEMAIN` is French, while a word of three
   letters or fewer stays an abbreviation and `CALL BOB MON 9 EST` stays English. A word inside
   a quote (`«»`, `»«`, `""`, `“”`, the German `„“`, the Romanian `„”`, and `‘’` or `''`
   closed at a word's edge, so `don't` stays a word) counts for no language, so
   `Quiero un recordatorio a las 9 para decirle «tak for i går» a Søren.` is Spanish; a message
   whose words outside quotes score nothing is read whole, so `"Rappelle-moi demain"` stays
   French ([readings](../readings/note-language-quotes.md)).
2. **English is the fallback.** A message with no match, or a tie the letters do not break, gets
   the English note. English is what every note was before, so a missing pick shows today's text.
   A message in a sixth language can get a third one: `Meu código mudou para 4862.` ties Spanish
   with Romanian and its `ó` picks Spanish. The forget readers read a message's language with
   `forget_language`, the same pick without letters and with quoted words counted, because they
   are frozen ([ADR-0075](ADR-0075-forget-chosen-memories.md) decision 7).
3. **Each translated note keeps its English constant** and adds a mapping from language to text
   beside it (`STORED_TIME_NOTES` beside `STORED_TIME_NOTE`); `in_language(english, others,
   language)` returns the English text for a language the mapping does not have. The readers that
   decide whether a note is due are unchanged.
4. **Every note `limit_notes` appends has a mapping**, and a note that fills words into its text
   writes them in the same language: `ROUNDS_SPENT_NOTE` its runs sentence (`runs_said`), with
   tool names as the tools name themselves and an approved handoff written as started, as
   `runs_line` writes it, `QUOTED_STORED_NOTE` the repeat and the time, and
   `WEEKLY_STORED_NOTE` the weekday names joined by the language's word for "and". A turn whose
   runs hand off (`hands_off`) gets `HANDED_ROUNDS_NOTE` instead, because the deep model's answer
   may follow it in the same reply: it says a handoff started, writes the handoff as started with
   nothing about its answer, and asks for nothing, so it is true whether or not an answer follows.
5. **A translated note states the same fact and the same next step as the English one**, in the
   form of address the model used in the recorded replies: `vous` in French, `Sie` in German, `tú`
   in Spanish and `tu` in Romanian.

## Consequences

- A note in another language is product text the maintainer reviews like any other; each
  translated note is listed in the commit that adds it.
- A message that changes language mid-chat gets the note in the language of its own message,
  which may differ from the reply's when the model keeps the earlier language.
- A note's text is not read back by any reader, so a translated note changes no later turn.
- A message whose one counted word is `ce` and that holds no letter outside ASCII keeps the
  Romanian note, the French `Note ce code: 5530.` as well as the Romanian `Ce faci?`, and a
  Romanian one beside a name holding a French letter (`Ce face José?`) gets the French note.
- A quote in another mark (the German `„“`, the Romanian `„”`, `‘’` or `»«`) is read as words,
  so `Erinnere mich, „thank you for the help“ zu sagen.` gets the English note.
