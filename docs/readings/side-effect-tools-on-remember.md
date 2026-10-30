# Readings: tools with a side effect called on a request to remember

How often a request to remember a fact makes the cortex call `set_volume` or `schedule_task`,
two tools that show no card, and whether a request that also asks for a reminder or a volume
change still calls them. Tonight's draws before this record found 3 `set_volume` calls in 88
requests to remember and 2 `schedule_task` calls in 32, one of which stored a yearly reminder
nobody asked for ([forget-request-wordings.md](forget-request-wordings.md#a-check-of-the-no-call-case-the-candidate-2026-10-30)).

## Rows and the rule, 2026-10-30

Written before the baseline was drawn. The rig is the `cortexn11` stack over `Converse` (the
cortex gemma-4-12B at context 16,384, schedules on, the Linux shell as the body), a new chat
for each draw, every card approved, `memories` empty at each draw's start. After each draw every
`memories` row it wrote is deleted, and every schedule it added is cancelled with
`RedisScheduleStore.cancel`.

| Row | Message | Draws | Tool asked for |
| --- | --- | --- | --- |
| R01 to R15 | the requests to remember of [forget-request-wordings.md](forget-request-wordings.md#a-check-of-the-no-call-case-rows-and-rule-2026-10-30), each its own row | 2 each | none |
| A01 | `Please remember this: I take my pills at 8 pm. Remind me every day at 8 pm to take them.` | 2 | `schedule_task` |
| A02 | `Note that my mother's birthday is on 12 May, and remind me of it the day before.` | 2 | `schedule_task` |
| A03 | `Remember to call the plumber tomorrow at 10.` | 2 | `schedule_task` |
| A04 | `Please remember this: I like my music quiet, so turn the volume down to 20%.` | 2 | `set_volume` |
| A05 | `Keep in mind that I am in a meeting now, so please mute the sound.` | 2 | `set_volume` |
| A06 | `Please remember this: I am hard of hearing. Set the volume to 80%.` | 2 | `set_volume` |

`asks_kept` (`memory_request.py`) reads every row above as a request to remember.

- An R draw fails when its turn calls `set_volume`, `get_volume` or `schedule_task`, read from a
  `ToolActivity` event or a card naming it. An A draw passes when its turn calls the tool its row
  asks for, whether or not the call succeeds; the Linux shell's volume call fails.
- The candidate leaves `set_volume` out of the tool list of a turn whose message `asks_kept`
  reads, unless the message names the sound, and `schedule_task` unless it asks for a reminder,
  and refuses a call to either by name on such a turn.
- The candidate ships when R01 to R15 fail in 0 of 30 draws, A01 to A06 pass in no fewer draws
  than the baseline's count less two, every A row that passes in a baseline draw passes in a
  candidate draw, and R01 to R15 store the fact in no fewer draws than the baseline's count less
  three.
- The baseline is every row with the shipped build. A baseline whose R draws call none of the
  three tools leaves tonight's 5 recorded calls as the defect's evidence; it then decides the A
  rows and the stored facts only. The null result is a candidate that fails any part of the
  rule: it is reverted and both tasks stay open.

## Baseline, 2026-10-30

Run log `base.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/def04344-43c5-4abe-b022-0038411a4a36/scratchpad/slot7/`,
the shipped build, the SM clock at 0.60 of its maximum at the start and 0.59 at the end.

| Rows | Result | What the draws did |
| --- | --- | --- |
| R01 to R15 | 2 of 30 fail | "my car is a red Fiat" called `set_volume` and `schedule_task`, both failed, and the reply said only that the car was noted; "my daughter is allergic to peanuts" called `set_volume` and `list_allowed_directories` |
| R01 to R15 | 29 of 30 store the fact | the peanuts draw stored nothing, since the file tool's result tainted the turn ([R-950](../refinements/tasks/950-a-request-to-remember-can-call-a-file-tool-and-store-nothing.md)) |
| A01 to A06 | 12 of 12 pass | each A01 to A03 draw stored its reminder; each A04 to A06 volume call failed and the reply said so; one A06 draw also called `schedule_task` |

The baseline is not the null result: 2 of 30 R draws called a tool with a side effect, beside the
5 recorded earlier tonight.
