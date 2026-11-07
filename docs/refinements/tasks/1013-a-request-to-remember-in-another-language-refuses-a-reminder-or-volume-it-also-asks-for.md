# A request to remember in another language refuses a reminder or volume it also asks for

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-07

`unasked_tools` (`unasked_tools.py`) leaves `schedule_task` and `set_volume` out of a turn whose
query `asks_kept` and names no use for them, read by `_REMINDER` and `_SOUND`. `asks_kept` now
reads French, German, Spanish and Romanian requests to remember, while those two readers name
only some of the words a request for a reminder or a sound change uses in those languages. A
message that asks to remember a fact and also asks for the tool loses the tool. Each of these
leaves the tool out (unit reproduction, `unasked_tools(query)`):

| Query | Tool left out |
| --- | --- |
| `Souviens-toi que j'ai rendez-vous chez le dentiste et préviens-moi demain à 9h.` | `schedule_task` |
| `Merk dir, dass ich morgen zum Zahnarzt muss, und sag mir um 9 Uhr Bescheid.` | `schedule_task` |
| `Ține minte că mâine am dentist și anunță-mă la 9.` | `schedule_task` |
| `Recuerda que me gusta así y sube la música.` | `set_volume` |
| `Souviens-toi que j'aime ça et monte la musique.` | `set_volume` |

Before the four languages were added, `asks_kept` was false on each of these and no tool was left
out. The English `Remember that I have the dentist tomorrow and give me a shout at 9.` loses
`schedule_task` the same way.

## What to do

1. Write the queries above as tests first, beside `test_unasked_tools_languages.py`.
2. Add the request forms: `préviens-moi`, `avertis-moi`, `Bescheid`, `avísame`, `anunță-mă`,
   `musique`, `música`, `muzica`, `plus fort`, `moins fort`, `más alto`, `mai tare`, and the English
   `give me a shout`.
3. Compare that with leaving a tool out only when the query names no time of day and no verb
   addressed to the assistant after the request to remember, which a word list cannot cover in
   every language; a reader that controls a refused tool fails toward keeping the tool.

## History

- 2026-11-07: filed by the audit of the reader of a request to remember in four more languages.
