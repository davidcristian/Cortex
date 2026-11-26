# Readings: the forget message forms left unread at the freeze

The forms of a forget message that no typed reader read when the readers were frozen on
2026-11-26 ([ADR-0075](../adr/ADR-0075-forget-chosen-memories.md) decision 7), each with the count
it was last measured at. Each form closed a backlog task, so its form and count are kept here.

## Method

Each count was taken with no model, at the tree of its date, by replaying generated or recorded
forget messages over seeded rows through the card's readers, with the call texts the linked record
names; a row marked drawn was taken on the stack brain with the rows seeded and every card
approved. The record column links the reading that holds the count, or names the scratch
directory of the run when no reading does. The direction says what the person ends up with:

- **kept**: a row the message asks to delete stays stored, the safe direction;
- **listed**: a row the message asks to keep, or does not ask for, is shown on the card, and is
  deleted only when the person approves the card;
- **withheld**: the turn is not recorded to memory;
- **note**: a note after the reply shows or does not show, with every row unchanged.

## Forms left unread at the freeze (2026-11-26)

| Form | Example | Count | Direction | Record |
| --- | --- | --- | --- | --- |
| A third person statement after `et`, `y`, `pero`, `și` or `dar`, read as an imperative to forget | `Il arrive en retard et oublie ses clés.` | 0 of 13,259 recorded strings (2026-11-08) | withheld | [replays](claim-reader-replays.md#a-forget-in-four-more-languages-and-an-english-keep-idiom-2026-11-08) |
| A later forget call holding the asked value beside another value or a phrase, after a delete left a deleted number held | `Forget my door code 5521.` with the later call `the locker code is 4412 and door 5521` | runs with its card in a unit probe; 0 of 8 later calls in 24 draws had the form (2026-11-09) | listed | [draws](forget-shared-number.md#the-n1v-draws-2026-11-09) |
| The Spanish and Romanian words for and (`y`, `și`) missing from `JOIN` | none: `JOIN` is read only beside an adding word, and no adding word is read in those languages | 0 rows listed or kept (2026-11-15) | none | [task](../refinements/tasks/1233-the-lead-words-of-a-forget-clause-are-not-read-from-the-table-of-forms.md) |
| A Romanian row named with its article `ul` outside a keep clause | `Uită dulapul 4242.` with the call text `4242` | 716 rows asked to delete kept over 42,356 generator messages; read in `names`, 23 rows not asked for and 90 either way listed (2026-11-21); read in `kept_rows` alone, 49 more rows asked to delete deleted, 6 rows not asked for listed over the word pairs and 10 rows marked neither way (2026-11-26) | kept | [task](../refinements/tasks/1282-a-romanian-row-named-with-its-article-outside-a-keep-clause-names-no-row.md) |
| The Romanian word for all, `toate` | `Uită toate 4242.` | 441 rows asked to delete kept over the generator; filled, 10 rows asked to keep and 36 not asked for listed (2026-11-26) | kept | [cells](forget-form-cells.md#the-cells-replayed-one-at-a-time-2026-11-24) |
| The words for only `seulement`, `nur`, `solo` and `doar` | `Vergiss alle 4242, nur die Karte.` | 535 to 972 rows asked to delete kept per word; filled, 53 to 114 rows not asked for listed, and 56 and 22 for `seulement` and `nur` once `alone` reads the rest (2026-11-26) | kept | [cells](forget-form-cells.md#a-word-for-only-read-as-a-limit-beside-another-clause-2026-11-26) |
| The Spanish and Romanian adding words `también` and `de asemenea` | `Olvida 4242, la tarjeta también.` | 1,076 rows asked to delete kept for `también`; filled, 36 rows not asked for listed (2026-11-24) | kept | [cells](forget-form-cells.md#the-cells-replayed-one-at-a-time-2026-11-24) |
| The Spanish words for the or my `el`, `los`, `mi` and `mis` beside an adding word | a row word after `mi` in a clause ending `también` | 180 more rows asked to delete kept than `también` alone keeps (1,256 against 1,076); filled, 4 more rows not asked for listed (2026-11-24) | kept | [cells](forget-form-cells.md#the-cells-replayed-one-at-a-time-2026-11-24) |
| A reply naming a kept row past the list of rows, before `from my memory` or a comma, or after `and the` or `and your` | `I've removed the locker code and phone number from my memory.` | 6 and 3 of 24 recorded false delete claims (2026-11-25) | note: the plain kept note shows, naming every kept row | [results](forget-result-texts.md#a-removal-continued-past-a-word-for-and-2026-11-25) |
| A word that only modifies a word for all, `other` or `single` | `Forget every other 4242.` | 498 rows asked to delete kept over the generator, 249 under each word, and 46 over the literal calls of the brain's forget tests (2026-11-25) | kept | [role](forget-everything-unread-role.md#a-word-of-the-message-no-stored-row-holds-2026-11-25) |
| A new value stated in French, German, Spanish or Romanian with a word for now or new | `Mein Alarmcode ist jetzt 5528.` beside a row holding `4826` | 3 of 3 statements probed name no old value (2026-11-25) | note: the old value note does not show | [old value](old-value-other-languages.md) |
| A forget of every value beside a negated keep clause naming a row of no kind | `Forget all 4242, not the locker.` | 546 of 576 rows asked to delete kept over the negated messages (2026-11-26) | kept | the `a3` scratch directory of the 2026-11-24 run |
| A request naming the forget tool before `to` and a forget verb | `Use your forget tool to forget what I told you about my dentist.` | drawn once, inside a request naming the escalate tool too: both forget calls refused and the dentist row kept (2026-11-26) | kept | `logs/draw2/` in the `s1` scratch directory of the 2026-11-26 run |
| An adding run that also holds a word for only | `Forget 4242, also the card only on the phone.` | 64 rows not asked for listed over the English generator (2026-11-26) | listed | [cells](forget-form-cells.md#a-word-for-only-read-as-a-limit-beside-another-clause-2026-11-26) |
| A Romanian plural that changes its stem or adds one letter | `Uită telefoanele.` | 64 rows not asked for listed over 640 plural cases, and `Uită cardurile.` with the call text `4242` keeps every row (2026-11-26) | listed | [plural](forget-romanian-plural.md) |
| A forget message quoting the verb every stored request opens with | `Forget what you remember about my card.` | 1,652 of 2,184 rows asked to delete kept (2026-11-26) | kept | [request verb](forget-request-verb.md) |
| An owner a possessive names, as `Don's phone` or `the phone of Don` | `Forget Don's phone 4242, don't delete the card.` | the person's own phone listed in 3 of the 8 `Don` cases that do not ask about it (2026-11-26) | listed | `don.json` in the `a1` scratch directory of the 2026-11-26 run |
| A forget of the lot, which holds no word for all, before a kept row | `Forget the lot the card stays.` | 2 of 30 probe cases list the row asked to keep (2026-11-26) | listed | [heads](forget-everything-unread-forms.md#heads-of-more-than-one-word-2026-11-26) |
| A word for only outside English, or in English outside a limit | `Oublie 4242, la carte aussi, seulement le téléphone.` | 324 rows asked to keep listed over 3,420 messages: 300 in the four other languages, 24 in English (2026-11-26) | listed | [cells](forget-form-cells.md#a-word-for-only-beside-a-call-naming-a-row-2026-11-26) |
| A Spanish or Romanian head of a forget of everything, a placing word after `todo` or `tot`, before a kept row | `Olvida todo de eso la tarjeta se queda.` | 10 of 144 placing cases list a row asked to keep, and 96 rows over the two generators of a head after another forget clause (2026-11-26) | listed | [heads](forget-everything-unread-forms.md#heads-of-more-than-one-word-2026-11-26), [after a clause](forget-form-cells.md#a-head-after-another-forget-clause-2026-11-26) |
| A word for only after a forget of everything no reader reads | `Wipe everything, only the card.` | 26 of 750 mixed messages list a row a reading keeps: 24 after `Wipe`, 2 in Romanian (2026-11-26) | listed | [cells](forget-form-cells.md#a-word-for-only-after-a-forget-of-everything-2026-11-26) |
| A word for only after a value of all | `Forget all 4242, only the card.` | 48 of 240 cases delete the row the word for only names, which a reading keeps (2026-11-26) | listed | [cells](forget-form-cells.md#a-word-for-only-after-a-forget-of-everything-2026-11-26) |
| A Romanian forget of everything except a row named with its article | `Uită tot în afară de dulapul.` with the call text `dulap` | 4 of the 26 rows asked to keep still deleted over 3,120 mixed cases (2026-11-26) | listed | [third audit](forget-form-cells.md#mixed-messages-of-the-third-audit-2026-11-26) |
| A deletion of a row's details outside English | `Efface tous les détails de ma carte de la mémoire.` with the call text `4242` | the card kept in all 24 cases in French, German, Spanish and Romanian (2026-11-26) | kept | [third audit](forget-form-cells.md#mixed-messages-of-the-third-audit-2026-11-26) |

One rule was tried for the Spanish and Romanian heads and not committed: the English scope rule
read in the head after an unread first word kept 60 of the 94 rows asked to keep still listed over
the 3,000 mixed cases, 40 of the 52 after another forget clause and 9 of the 10 placing cases, and
listed none newly, but kept 120 rows asked to delete over the mixed cases and 20 over the placing
cases, all scope forms such as `Vergiss alles von meiner Karte.` (`trees/r66` in the `x2` scratch
directory of the 2026-11-26 run).
