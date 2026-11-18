# A handoff that a restart of the brain ends

What a chat's store holds, and what the next replies say, after the brain's container is killed in
the middle of a handoff to the deep model. Decisions 3 and 6 of
[ADR-0074](../adr/ADR-0074-replayed-tool-runs.md) rest on it.

## Reading, 2026-11-18

The default stack with escalation on, the Qwen3.8-27B Q4 deep tier, the model host on build
`b12375` and a brain image built from the tree. One draw per row. Method: `live.sh` in
`~/.cache/cortex-run/2026-11-18/slot13/` sends each turn with `turn13.py`, kills the brain's
container once the deep tier answers `ready`, starts it again and reads the chat's list from
redis; the log is `logs/live.txt` beside it.

Chat A, whose handoff the kill ended:

| Step | What was read |
| --- | --- |
| The handoff turn, cut by the kill | memory row with `Tools run: escalate_to_brain (handoff started, answer not recorded here)` |
| Boot | the brain logged `a handoff did not survive the restart; marking it failed`; the deep tier was stopped and the cortex and both GPU subagent servers answered `ready` |
| The chat's list in redis after the restart | three messages: the request, the cortex's reply with the run `escalate_to_brain` `ok: true`, and a third reply of the same turn with the run `escalate_to_brain` `ok: false` and the text of `UNANSWERED_HANDOFF_NOTE` |
| Next turn, `What is 5 plus 5?` | `5 plus 5 is 10.` with `UNANSWERED_HANDOFF_NOTE` under it |
| The turn after it, `And what is 6 plus 6?` | `6 plus 6 is 12.` and no note |
| A new chat, `What did I last ask you to hand to the deep model, and did it finish?` | the cortex named the request, said it did not finish because the assistant restarted during the handoff, and offered to hand it over again |

Chat B, whose handoff completed on the same stack after the restart:

| Step | What was read |
| --- | --- |
| The handoff turn | the cortex's sentence and the deep model's answer in one reply; two memory rows, the cortex's with the `handoff started` line and the deep model's with no `Tools run` line |
| Next turn, `What is 7 plus 7?` | `7 plus 7 is 14.` and no note |
| The chat's list in redis | five messages, none with a failed `escalate_to_brain` run |

The new chat's reply in chat A's table is the model's own reading of two recalled memory rows: no
check of the brain's produced it ([R-1257](../refinements/tasks/1257-a-handoff-a-restart-ended-is-told-only-in-its-own-chat.md)).
