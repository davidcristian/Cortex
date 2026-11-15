# Readings: an English store request and the tools it did not ask for

What `unasked_tools` and `unasked_sidecar_tools` (`unasked_tools.py`) do on an English request to
store one stated fact, such as `Save my phone number 0721 555 019.`, once both read `fact_stored`
(`fact_request.py`) beside the request to remember. The decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md); the reader of the request itself is measured
in [forget-refusal-stated-fact.md](forget-refusal-stated-fact.md).

## What changed in the readers

The start build is `5d5c44ea4`. Its two readers act only on a message `asks_kept` or
`asks_kept_alone` (`memory_request.py`) reads, so a store request kept every tool. The fix reads
`_stores_a_value` (`unasked_tools.py`) beside them: `fact_stored` (`fact_request.py`) reads the
message (an opening `save`, `store`, `keep`, `record`, `memorize`, or `write`, `note` or `jot`
with `down`, then one sentence stating a fact), and the fact is a statement with `is`, `are`,
`was` or `were`, or its value follows `number`, `code`, `PIN`, `password`, `passcode`, `address`
or `birthday`. `stores_fact` alone also reads `Save my draft 2.`, `Record my screen for 10
seconds.` and `Keep my volume at 40.`, where the same verb saves a file or asks for an action, so
any other object keeps every tool. `unasked_tools` searches only the fact for a second action,
since `actions_asked` reads the store verb itself as one.

## Replay through the start build and the fix

Every string literal of `brain/packages/*/tests` in the fix, every backticked span of
`docs/readings`, `docs/refinements/tasks`, `docs/host/tasks` and `docs/adr`, the last person
message of every request in the run's proxy log, and eight store requests in Italian, Portuguese,
Dutch and Polish: 26965 strings. Each went through both readers of both builds, with the ten file
tools and `spawn_subagents` listed. The start build leaves a side effect tool out on 814 strings
and refuses the sidecar tools on 803; the fix on 838 and 823. 25 strings changed, each from every
tool kept, and each opens with a store verb before a fact the fix reads:

- 13 lose both side effect tools and have the sidecar tools refused: `Save my phone number 0721
  555 019.`, `Keep my phone number 0721 555 019.`, `Memorize my phone number 0721 555 019.`,
  `Write down my phone number 0721 555 019.`, `Store this: my phone is 0721 555 019.`, `Please
  save that my code is 4242.`, `Write this down: our wifi password is hunter2`, `Save my door code
  4417.`, `Record our gate PIN 0042.`, `Keep my passport number X1234567.`, `Store my address 12
  Mill Lane.`, `Save that my shoe size is 43.` and `Store this: my draft is ready.`
- 7 have the sidecar tools refused and keep a side effect tool the fact names or a second clause
  asks for: `Store this: my alarm code is 4242.`, `Save this: my alarm code is 5528.`, `Record
  that my alarm code is 5528.` and `Store my alarm code 5528.` keep `schedule_task`, `Save that my
  speaker volume is 40.` and `Save my code 4242 and mute it.` keep `set_volume`, and `Save my code
  4242 and ring me.` keeps both.
- 5 lose both side effect tools and keep the sidecar tools for a source they name: `Save this: my
  report is in /tmp.`, `Store that our file is report.pdf`, `Keep it: my draft is 2 pages.`, `Save
  my email address ana.pop@example.com` and `Save that my code is 4242 and list files`.

No Italian, Portuguese, Dutch or Polish string changed (`Salva il mio numero 0721 555 019.`,
`Guarda o meu número 0721 555 019.`, `Bewaar mijn nummer 0721 555 019.`, `Zapisz mój numer 0721
555 019.`). `Save the report to my notes folder.`, `Store this file in /tmp.`, `Save my draft
2.`, `Save my report 2024.`, `Save my invoice 20391.`, `Save my address book 2.`, `Record my
screen for 10 seconds.` and `Keep my volume at 40.` keep every tool on both builds.

## The store turn: rows and the rule

Written 2026-11-15 before any draw. The start build runs as the side brain `cortexn23-side-start`
(port 23061, `git archive 5d5c44ea4`) and the fix as `cortexn23-side-fix` (port 23062, built from
the working tree), each with its own database, both against one model host (engine build
`b12375-9d25e0014`, gemma-4-12B QAT q4_0 with its projector, context 16384) through the recording
proxy. Both list the body tools, the schedule tools, `forget_memories` and the ten file tools of
the filesystem sidecar, 19 in all. Each draw empties the build's `memories` table first and is a
new chat, and every card is approved.

- **s**, 12 draws per build: `Save my phone number 0721 555 019.` Counted per build: draws with a
  file tool call, whether each call ran or was refused, draws with a forget call, draws whose reply
  shows the unkept note, and draws that end with a row holding `0721 555 019`.

The rule: the fix holds when every fix draw that calls a file tool has the call refused and ends
with the phone row stored, and when the fix stores the phone row in at least as many draws as the
start build. How often the form occurs (draws with a file tool call) is counted apart, per build.
If no fix draw calls a file tool, the first part decides nothing and this record says so. The first
request of the two builds differs, since the fix leaves `set_volume` and `schedule_task` out of the
list, so the second part compares the builds. If the fix stores the row in fewer draws than the
start build, the readers stay as they are and the task stays open.

`Save the report to my notes folder.` and `Store this file in /tmp.` get no draw: both readers
return the same sets for them on both builds, so both builds send the same first request and a
draw would count only draw noise.

## The store turn: what was drawn

Drawn from 03:46 to 03:57 on 2026-11-15, the start build's 12 draws first (proxy log lines 51 to
82) and then the fix's 12 (lines 84 to 119), SM clock 0.58 to 0.59 of `clocks.max.sm`. Logs
`draw-start.log` and `draw-fix.log`, rows `draws-start.jsonl` and `draws-fix.jsonl`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/bd106a1a-a17f-4ca5-8841-82294e4917a8/scratchpad/slot1/`.
The start build's first request lists 19 tools and the fix's 17, without `set_volume` and
`schedule_task`.

| Row | Build | Draws | Draws with a file tool call | Draws with a forget call | Phone row stored |
| --- | --- | --- | --- | --- | --- |
| s | start | 12 | 3, each call ran | 0 | 9 |
| s | fix | 12 | 0 | 0 | 12 |

**Result: the second part of the rule holds, 12 of 12 against 9 of 12, and the first part decides
nothing, since no fix draw called a file tool.** Each start build file call was
`list_allowed_directories`, and one of those draws also called `set_volume`, which failed with no
body listening. No fix draw called any tool. What the brain does with a file call on this message
is therefore read from the test of the tool loop alone: the call is refused by name and the turn
is kept.

## The note on a store turn that stores nothing: rows and the rule

Written 2026-11-15 after row s was drawn on the start build and before any draw on the note build.
In row s the start build stored nothing in 3 draws, each reply held `I've saved your phone
number: 0721 555 019.`, and none showed `UNKEPT_CLAIM_NOTE`: `claims_kept` (`memory_claim.py`) reads
`saved` only before `in memory`, and `unkept_note_due` reads the request with `asks_kept`, which
reads no store verb. The note build is the start build with one change, `unkept_note_due` reading
`stores_fact` beside `asks_kept`, so its file tools still run. It runs as `cortexn23-side-note`
(port 23063) under the conditions of row s.

- **n**, 12 draws on the note build: `Save my phone number 0721 555 019.` Counted: draws that end
  with no phone row, and of those the draws whose reply ends with the note.

The rule: the note change holds when every n draw that stores nothing shows the note and no n draw
that stores the row shows it. If every n draw stores the row, the row decides nothing and
[task 1202](../refinements/tasks/1202-a-store-request-whose-turn-stores-nothing-shows-no-note.md)
stays open with this row as its next one.
