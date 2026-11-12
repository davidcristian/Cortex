# Plain forgets replayed through the destructive card

Plain forgets that name one row, replayed through the `forget_memories` card and delete, to check
that the keeps added on 2026-11-12 (the last group keep beside a whole value, the last group keep
when the message names words none of the row's, and the keep of both rows when a forget cannot
tell a card from a code) leave every plain forget listing the row it names.

## Method

Taken 2026-11-12. A script built each row set in an `InMemoryMemoryStore`, sent one
`forget_memories` call through `ForgetChosenTool.card` and `invoke`, and recorded the deleted rows.
It ran once on the code of the start build (`d1620de90`) and once on `4cf6daf78`, the same
strings each time, with the calling chat either the chat that stored the rows or a new one.

- **Rows.** A card (`4111 1111 1111 4242`), an IBAN (`RO49 AAAA 1B31 0075 9384 0000`), a phone
  number (`0721 555 019`) and a gym code (`4242`), each stored in English, plus the card stored in
  French and in German.
- **Row sets.** 13: each fact alone, the card and IBAN in both orders, card, IBAN and phone in
  two orders, the French or German card beside the IBAN or the phone, and the card beside the gym
  code in both orders.
- **Messages.** 20 forgets naming one row by its words, its value, or both, in English, French
  and German, for example `Forget my IBAN.`, `Forget 0721 555 019.`, `Oublie la carte qui finit
  par 4242.` and `Vergiss die Karte, die auf 4242 endet.` Each was sent with one to three call
  texts the model writes: the value, a word of the row, or the last group the message names.

548 cases in all.

## Readings

| Message and row language | Cases | Listed at the start build | Listed after the keeps |
| --- | --- | --- | --- |
| Same, call text in the row | 224 | 224 | 224 |
| Same, call text a word the row lacks (`card` on a French row) | 8 | 0 | 0 |
| Different | 316 | 196 | 190 |

- **Same language.** Every plain forget whose call text the row holds listed the named row in both
  builds. The only difference between the builds in this group is an improvement: `Forget my gym
  code 4242.` and `Forget the code 4242.` beside the card ending in 4242 deleted both rows at the
  start build and only the gym code after the keeps (8 cases).
- **Different language.** The 6 new misses are `Oublie la carte qui finit par 4242.` and `Vergiss
  die Karte, die auf 4242 endet.` with call text `4242` over the English card beside the English
  gym code: the start build deleted both rows, the keeps delete neither. The 120 misses common to
  both builds are a message naming a row only in words of another language than the row's, such
  as `Vergiss meine Telefonnummer 0721 555 019.` over the English phone row, which `unnamed` keeps
  because the message names words, none of the row's. Task
  [1158](../refinements/tasks/1158-a-forget-in-one-language-keeps-a-row-stored-in-another.md) has
  the reproduction.

## Rules from earlier nights

Taken 2026-11-12. The 53 test files of the start build whose names hold `forget`, `claim`,
`closing`, `unasked`, `memory_request`, `refus` or `just_said` ran against `4cf6daf78` with the
brain's pytest settings: 3163 passed and 23 failed. Every failure is a reply that now ends with
`UNCALLED_FORGET_NOTE` on a forget request with no forget call (`test_closing_notes.py`,
`test_memory_claim.py`) or a test passing no forget run beside an inside or longer note
(`test_forget_inside_language.py`), in the four test files that now expect those notes. No test of
the newest row rule, the keep clause readers, the one IBAN group rule or the refusal of an unasked
forget changed its result.

## Notes on one reply

Read from `limit_notes` on 2026-11-12. `UNCALLED_FORGET_NOTE` shows only when no run of the turn
is a forget, and a card's Deny and a call that matched nothing are runs, so it never shows beside
`DECLINED_FORGET_NOTE`, `UNMATCHED_FORGET_NOTE`, `kept_note`, `inside_note` or `longer_note`. It
can show beside `UNKEPT_CLAIM_NOTE` and `KEPT_BEYOND_CHAT_NOTE`, which say nothing about a delete.
A refused call is not a run, and the note says no forget call ran, which stays true. Every note
`limit_notes` writes has the same four translations, picked by `message_language` once per reply.
A cortex reply that hands the turn to the deep model with an approved `escalate_to_brain` run gets
no note, because the deep model can still delete in the same turn; the deep model's reply gets it
when neither model made a forget call.
