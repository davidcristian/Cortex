# Readings: requests in other languages and local time forms

What the brain does with a request written in French, German, Spanish or Romanian, with a time or
date in a local form, with a decimal comma, a currency or a name with diacritics, and with a
message that mixes two languages. A flow passes when the right tool runs, the stored row or
schedule holds what the person asked for, and the reply is in the person's language. The typed
readers of the person's message and of the reply are English-first, so each flow also checks
whether a non-English form reaches the reader it needs or passes it unread. Scheduling is
[ADR-0025](../adr/ADR-0025-scheduling-reminders.md), memory
[ADR-0008](../adr/ADR-0008-memory-v1.md).

## The rig

**2026-11-07**, the `cortexn15` GPU stack at the tree of that night: the resident cortex
(gemma-4-12B, llama-server build `b12169-3ed7284f2`) at a context of 16,384 tokens, memory on
pgvector with the default `global` scope, schedules on with the Redis backend and the schedule zone
`Europe/Berlin`, the brain's clock on Saturday 7 November. Turns ran over `Converse` from the host
driver with every card approved, each chat named `l8-<flow>`, and one flow ran on the Linux shell
([body-overlay.md](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless)) on `Xvfb`. SM
clock at the flows: 0.69 of `clocks.max.sm`. After each batch one script read every
`cortex:schedule:*` record and the `memories` table. Run logs: `flows1.log` to `flows3.log` and
`turns1.jsonl` to `turns3.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot8/`.

## 1. The tools in four languages

One chat per language: set a reminder, remember a fact, ask what is scheduled. Then one new
English chat per fact asked for it back.

| Message | Tools | Stored | Reply language |
| --- | --- | --- | --- |
| `Rappelle-moi d'appeler ma sœur demain à 17h30.` | `schedule_task` | 8 Nov 17:30, `Appeler ma sœur` | French, plus an English note |
| `Souviens-toi que le code de mon casier à la piscine est 7731.` | `spawn_subagents` | exchange row | French |
| `Qu'est-ce qui est prévu ?` | `list_scheduled` | none | French |
| `Erinnere mich morgen um 9 an den Zahnarzttermin.` | `schedule_task` | 8 Nov 09:00 | German |
| `Merk dir, dass mein Hund Bello heißt.` | `spawn_subagents` | exchange row | German |
| `Was ist geplant?` | `list_scheduled` | none | German |
| `Recuérdame pagar el alquiler el 3 de abril a las 10.` | `schedule_task` | 3 Apr 2027 10:00 | Spanish |
| `Recuerda que mi color favorito es el verde.` | none | exchange row | Spanish |
| `¿Qué tengo programado?` | `list_scheduled` | none | Spanish |
| `Amintește-mi să sun la bancă vinerea viitoare la ora 14:00.` | `schedule_task` | Fri 13 Nov 14:00 | Romanian |
| `Ține minte că numărul apartamentului meu este 42.` | none | exchange row | Romanian |
| `Ce am programat?` | `list_scheduled` | none | Romanian |

Every stored time was right in the schedule zone, including 3 April across the change to summer
time (08:00 UTC). The lists named every reminder of every chat, since the schedule is not per
chat, and translated the other languages' reminder texts in brackets. Two of the four requests to
remember called `spawn_subagents` after a trace that looked for a `remember_memory` tool, and the
call ran, where the brain refused the same call on the English requests of section 3
([task 995](../refinements/tasks/995-a-request-to-remember-spends-its-thinking-looking-for-a-tool-to-store-the-fact.md)).

| English question, new chat | Reply |
| --- | --- |
| `What is my swimming pool locker code?` | `Votre code de casier à la piscine est 7731.` |
| `What is my dog called?` | `Dein Hund heißt Bello.` |
| `What is my favourite colour?` | `Your favorite color is green.` |
| `What is my apartment number?` | `Numărul apartamentului tău este 42.` |

The embedder found every fact across languages, but three of four replies were in the language of
the recalled row rather than the person's. A fourth reply of the same kind came in section 2: the
English `Remind me at half past five to call mum.` was answered in French, after the French
reminder row was recalled into its request. Filed as
[task 997](../refinements/tasks/997-a-reply-takes-the-language-of-a-recalled-memory.md).

## 2. Times and dates in local forms

Each in a new chat; Saturday 7 November at about 03:52 on the brain's clock.

| Message | Stored | Reply |
| --- | --- | --- |
| `Remind me at 17h30 to take the bins out.` | today 17:30, once | names 17:30 |
| `Erinnere mich um 17:30 Uhr an die Wäsche.` | **17:30 every day** | `ich habe dich für 17:30 Uhr an die Wäsche erinnert` |
| `Remind me at half past five to call mum.` | today 17:30 | French, names 17h30, plus the English note |
| `Remind me at 5.30pm to water the plants.` | today 17:30 | names 5:30 PM |
| `Rappelle-moi le 3 avril de renouveler mon passeport.` | 3 Apr 2027 09:00 | names 09:00 |
| `Erinnere mich am 4. März an den Elternabend.` | 4 Mar 2027 09:00 | names 09:00 Uhr |
| `Remind me on 03/04 to file the tax form.` | 4 Mar 2027 09:00 | `March 4th, 2027`, plus the note |
| `Remind me next Friday at 10 to send the report.` | Fri 13 Nov 10:00 | names 13 November |
| `Erinnere mich jedes Jahr am 4. März an den Geburtstag meiner Mutter.` | yearly 4 Mar 09:00 | names every 4 March |
| `Remind me every year on 4 March about my mother's birthday.` | none new | names the German reminder as already set |
| `Recuérdame cada año el 12 de octubre el cumpleaños de Ana.` | yearly 12 Oct 09:00 | no time, plus the English note |
| `Erinnere mich drei Tage vor dem 4. März an das Geschenk für meine Mutter.` | yearly 1 Mar 09:00 | names every 1 March |
| `Rappelle-moi le 15 de chaque mois de payer le loyer.` | monthly on the 15th, 10:00 | names `10h00`, plus the English note |

Every date reached the right typed argument without the English readers: the German and Spanish
yearly requests used `on_dates`, the French monthly one `on_month_days`, the German three days
before 4 March stored 1 March. The yearly and offset readers (`schedule_yearly.py`,
`schedule_offset.py`) never ran on these turns, since nothing called for a refusal, so a German or
French form that does need one is not tested here. `03/04` was read month first, as 4 March, in a
schedule zone where day first is usual; the reply named `March 4th`, so the person sees the
reading.

Two defects. The German `17:30 Uhr` request was stored as a daily repeat and the reply did not
say so ([task 998](../refinements/tasks/998-a-one-time-reminder-in-german-is-stored-every-day.md)).
And the note the brain appends when a reply names no stored time
(`STORED_TIME_NOTE`, `schedule_claim.py`) was added under replies that named it as `17h30` and
`10h00`, because `names_time_of_day` read only English clock forms. That reader now also reads
`17h30`, `9 h 15`, `9 Uhr` and `9.30 Uhr`, and not a duration such as `in 2h30` or
`dans 2h30`. Replayed through the old and the new reader, 1 of the 195 distinct replies recorded
that night changed, the French list reply that names `17h30`. Notes in English under a reply in
another language are [task 999](../refinements/tasks/999-a-note-the-brain-appends-is-english-under-a-reply-in-another-language.md).

## 3. Numbers, currencies and names with diacritics

`Remember that Ștefan owes me 12,50 € for the pizza.`, the same for `Jürgen Müller's flat rent is
1.234,56 € per month` and `José Ramírez's birthday is 9 June`, each in a new chat, then a new chat
per question. Each stored row kept the letters, the decimal comma, the thousands point and the
euro sign as typed, and each answer repeated them exactly. On the Linux shell, a new chat asked
`How much does Ștefan owe me, and what is Jürgen Müller's rent?`; the overlay painted the title,
the question and the answer with every character intact, and the title cut off with an ellipsis
at the window's width. Frame: `diacritics.png` in the run log directory. Two of the three requests
to remember called `spawn_subagents`, and the brain refused both, since `asks_kept` reads them as
requests to remember. No defect.

## 4. Messages in two languages

| Message | Tools | Result |
| --- | --- | --- |
| `Can you remind me mâine la 8 to call the doctor, bitte?` | `schedule_task` | 8 Nov 08:00, reply in English |
| `Remember que mi hermana se llama Lucía, and remind me tomorrow at 18:00 to call her.` | `forget_memories`, `list_scheduled`, `schedule_task` | 8 Nov 18:00; reply says the name was not saved |

The second reply ended `I couldn't find any previous memory about your sister's name, so I
haven't "saved" it as a long-term memory`, while the exchange was stored as a `memories` row. The
forget call matched nothing. The English form of the same message gets the same treatment from
the typed readers (`unasked_forget` returns nothing for a message that also asks for a reminder),
so this is not a language gap
([task 1001](../refinements/tasks/1001-a-request-to-remember-with-a-reminder-says-the-fact-was-not-saved.md)).

## 5. Forget in other languages

| Message | Card | Deleted | Reply |
| --- | --- | --- | --- |
| `Oublie le code de mon casier à la piscine.` | approved | 1 of 3 rows naming `7731` | `C'est fait, j'ai oublié le code` |
| `Vergiss, wie mein Hund heißt.` | approved | both rows naming `Bello` | `Ich habe das vergessen.` |
| `Olvida mi color favorito.` | denied | none | says the action was denied |

The French call forgot the phrase `code de mon casier à la piscine`, which the two recall
exchanges (`Votre code de casier à la piscine est 7731.`) do not contain, so a new English chat
asking for the code was answered `7731` again
([task 1002](../refinements/tasks/1002-a-forget-by-phrase-leaves-the-recalled-value-in-other-rows.md)). After the
German forget, `What is my dog called?` searched the file tools and said it had no record.

## 6. Requests in other languages and the English readers

`asks_kept` (`memory_request.py`) reads only English. A French or German request to remember is
therefore not read as one: the refusal of unasked tools did not run, and the `spawn_subagents`
calls of section 1 ran, where the English requests of section 3 had the same call refused
([task 1000](../refinements/tasks/1000-a-request-to-remember-in-another-language-is-not-read-as-one.md)).

`asks_not_kept` read only English too, and that one decides whether a turn is stored. Each
message below ran in a new chat:

| Message | Stored | Reply |
| --- | --- | --- |
| `Mon code PIN de la banque est 9911, mais ne le retiens pas.` | **yes** | `je ne retiendrai pas cette information` |
| `Mein Garagencode ist 4402, aber merk dir das nicht.` | **yes** | `werde ihn aber nicht in meinem Gedächtnis speichern` |
| `My garage code is 5503, but don't remember it.` | no | says it will not save it, plus the unkept note |

The French and German replies told the person the code was not kept while the brain stored it and
would recall it in every later chat. `asks_not_kept` now also reads a negative imperative of a
keep verb that opens a clause in French, German, Spanish and Romanian, and not a statement with
the same verb (`je ne retiens pas`, `ich kann mir das nicht merken`, `no recuerdo`,
`el nu reține`). Replayed through the old and new reader, of the 72 distinct messages in the
night's turn records only these two changed, and of 21,645 distinct strings in the brain's test
files and the readings records only the new tests' own did.

## 7. The same turns on the build with both readers

The stack brain was rebuilt from the tree with both readers widened, and three new chats ran at
04:19. `Mon code PIN de la banque est 6620, mais ne le retiens pas.` and
`Mein Garagencode ist 3318, aber merk dir das nicht.` stored no `memories` row (0 rows name
either code), and `Rappelle-moi demain à 17h30 de sortir les poubelles.` stored the reminder with
a reply naming `17h30` and no note.
