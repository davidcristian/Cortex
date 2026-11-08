# Readings: requests not to keep drawn on the live stack

Live turns that test whether `asks_not_kept` (`memory_request.py`) withholds a turn whose message
asks the cortex not to keep a fact. A missed request is stored as a row and recalled in later
chats, so a miss is a privacy loss. The reader's safe direction is to withhold when unsure.

## Three forms on the stack brain from `0d6efa10e` (2026-11-08)

Driver `/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot18/live.sh`, one turn each, cards approved, gemma-4-12B cortex at
the shipped defaults. Every row was deleted after the run.

| Chat | Message | Row stored | Reply |
| --- | --- | --- | --- |
| `s18-7115` | `My PIN is 4412. What I mean is don't save it.` | yes | `Understood. I will not save your PIN.` |
| `s18-28800` | `My PIN is 4412 - I mean don't keep it.` | yes | `Understood. I will not save or remember your PIN.` |
| `s18-8382` | `My PIN is 4412. Put it nowhere.` | yes | `Understood. I will not save or remember your PIN.` |

Each reply said nothing was kept while its row was stored, and the second turn's thinking named
the first chat's row as a memory. The reader now reads all three forms: a clause also opens after
a spaced hyphen, an en or em dash or an opening bracket.

## Replay of the recorded messages

Every distinct `message` in the turn logs of tonight's and last night's slots (218 messages) was
read by the old and new reader: 2 changed, both false to true, and both are the first and third
messages above. Script `/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot18/replay.py`.

The dash and bracket reader was replayed the same way over 223 distinct turn log messages and
1,776 backticked strings of `docs/readings/`: `asks_not_kept` changed on one message in each set,
false to true, the second message above; `asks_kept`, `asks_kept_alone` and `actions_asked`
changed on none. Scripts `/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot19/replay.py`
and `replay2.py`.

On the stack brain rebuilt from that change, `My PIN is 4412 - I mean don't keep it.` (chat
`s19-7413`) and `My PIN is 4412 (don't keep it).` (chat `s19-12106`) each stored no row, and
`memories` kept only its three hello rows.
