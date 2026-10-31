# Readings: listing the side-effect tools on a request to remember

Leaving `set_volume` and `schedule_task` out of the tool list of a request to remember raised the
cortex's `forget_memories` calls from 1 of 30 to 13 of 30
([separated pair](side-effect-tools-on-remember.md#the-forget-calls-on-a-request-to-remember-separated-pair-the-draws-2026-10-31)).
This record holds the check of keeping both tools listed and refusing a call to either by name
([R-961](../refinements/tasks/961-a-request-to-remember-a-stored-fact-can-show-a-forget-card.md)).

## Rows and the rule, 2026-10-31

Written before either build was drawn. The rig is the `cortexn12` stack over `Converse`: the cortex
gemma-4-12B at context 16,384, llama-server build `b12004-3c809f443`, schedules on, the Linux shell
as the body, a new chat for each draw. Baseline is the stack's brain, built from `6e9462fe6`, which
leaves both tools out. The candidate is a brain beside it that lists both tools and still refuses a
call to either by name as `UNASKED`, on a turn whose message names no use for them. The two are
drawn in turn, and the build that goes first alternates by row and by pass.

| Row | Message | Pool at the draw's start | Cards | Draws |
| --- | --- | --- | --- | --- |
| R01 to R15 | the requests to remember of [the rows above this record](side-effect-tools-on-remember.md#rows-and-the-rule-2026-10-30) | empty | approved | 1 on each build |
| S01 to S06 | R01, R02, R12, R05, R07 and R09 | one stored exchange holding that fact, written by a real turn | approved in pass 1, denied in pass 2 | 2 on each build |
| A01 to A06 | the requests that also ask for a reminder or a sound change, of the same rows | empty | approved | 1, candidate only |

The S rows are the six the pair's "after" build called most often, with one stored exchange each.
Only they can show a forget card, since `card` (`memory_forget_chosen.py`) lists what the text
matches. An approved card deletes the stored fact and a called forget keeps the new turn out of
memory unless every call matched nothing, so an approved card can lose the fact, and a denied card
keeps the old row and drops the new exchange. A refused call shows no `ToolActivity` event, so
refusals are counted from the brain's `tool.invocation` audit lines by session.

The candidate ships when all of these hold:

1. R01 to R15 call `forget_memories` in at most 3 of 15 candidate draws and at least 3 fewer than
   baseline draws. A baseline under 3 of 15 is no result: both builds are then drawn once more over
   R01 to R15, and the bound is read over 30 draws as at most 6 and at least 5 fewer.
2. S01 to S06 show no more forget cards on the candidate than on the baseline, and a row holds the
   fact after the draw in no fewer candidate draws than baseline draws.
3. No R or S draw on the candidate runs `set_volume`, `get_volume` or `schedule_task`, read from a
   `ToolActivity` event, a card or an added schedule. This is the rule of
   [R-901](../refinements/tasks/901-a-request-to-remember-a-fact-can-set-the-volume.md), now tested
   on calls the model can make.
4. No candidate reply says the volume changed or a reminder was set, and at most 3 of the 27
   candidate R and S draws mention the volume or a reminder at all.
5. R01 to R15 store the fact in no fewer candidate draws than baseline draws less one.
6. A01 to A06 call the tool their row asks for in at least 5 of 6 candidate draws. They called it in
   12 of 12 on 2026-10-30, and the candidate changes only the other tool's listing.

The null result is a candidate that fails item 1: listing the tools does not bring the calls down,
so the pair's rise has another cause, the candidate is reverted and the task stays open. A candidate
that passes item 1 and fails any other item is reverted too, and the task names what it cost.

## The draws, 2026-10-31

Run log `draw961.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot3/`,
the SM clock at 0.09 to 0.22 of its maximum. No draw ended in an error, every S draw started with one
`memories` row, and every other draw with none. The S rows' exchanges came from real turns on the
baseline. Each brain was checked before the draws: the stack's leaves both tools out and the
candidate lists them.

| Rows | Baseline | Candidate |
| --- | --- | --- |
| R01 to R15 calling `forget_memories` | 4 of 15 | 5 of 15 |
| R01 to R15 storing the fact | 15 of 15 | 15 of 15 |
| S01 to S06 showing a forget card | 1 of 12 | 3 of 12 |
| S01 to S06 holding the fact after the draw | 11 of 12 | 11 of 12 |
| R and S running a tool with a side effect | 0 of 27 | 0 of 27 |
| R and S replies mentioning the volume or a reminder | 1 of 27 | 0 of 27 |
| R and S with a refused call | 0 of 27 | 1 of 27 (R02) |

**Item 1 fails, so this is the null result.** Listing the tools did not bring the calls down, and
item 2 fails too. The candidate is not shipped: both tools stay out of the list. The A rows were not
drawn, since item 1 had decided it.

Four things the draws show:

- **A card on a stored fact costs the fact.** Each of the 2 approved cards, one on each build, deleted
  the stored row, and the new turn was kept out of memory, so no row held the fact afterwards. The
  person had asked to remember it. Each reply said it was noted or could not be saved, and the note
  that nothing was kept went beside it on the candidate. Each of the 2 denied cards, both on the
  candidate, kept the old row and dropped the new exchange
  ([R-961](../refinements/tasks/961-a-request-to-remember-a-stored-fact-can-show-a-forget-card.md)).
  The S rows without a card stored a second row beside the first.
- **The pair's 1 of 30 did not repeat.** The candidate lists the same tools as the pair's "before"
  build and drew 5 of 15. Reading the changes between those two builds found none to the tool list, a
  tool's text or the system message; that is an assumption until a recording of both first requests
  is compared. Over every run so far, each on its own build and night, the builds that leave the tools
  out drew 43 of 120 and those that list them 11 of 75. So the list may still move the calls, by less
  than the pair showed, and this run could not see it.
- **A listed tool can be called and refused without harm to the fact.** The refused R02 call left the
  turn untainted and stored the fact, and the reply did not name the call.
- **That R02 draw took about 10 times the row's median.** The cortex wrote its reply, then `set_volume`
  calls with no arguments until the length limit, and the reply ended in the limit note
  ([call-run-cut.md](call-run-cut.md)).
