# Readings: the reminders off note

With no schedule store configured (`CORTEX_SCHEDULE_BACKEND=none`, the compose default) the cortex
is offered no scheduling tool, and a reply to a reminder request could still say the reminder was
set or would fire. The brain now closes a turn whose message `asks_reminder` (`unasked_tools.py`)
reads, or whose reply claims a schedule, with `REMINDERS_OFF_NOTE` (`schedule_off.py`) in the
message's language: `(Reminders are off here, so nothing in this turn was scheduled.)`. It is true
on every turn it reaches because no store exists, and it replaces the unscheduled claim note there,
whose request to list the reminders has no tool to answer it. These rows were drawn before and after
that change, on the rule written into the task before the first draw.

## The rig

**2026-11-28.** Compose project `cortexn33` on plain compose defaults: `CORTEX_SCHEDULE_BACKEND`
unset, so `none`, and escalation off, so the cortex is offered one tool, `forget_memories`. Before:
the brain image built from the tree without the change. After: the same image with the changed
`cortex_core` and `cortex_orchestrator` bound over its packages. The model host ran from its
existing image with the tree's model manager and core bound over its packages, and started the
cortex as:

```
llama-server --model /models/unsloth/gemma-4-12B-it-qat-GGUF/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf
  --host 0.0.0.0 --port 8080 -ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram 8192
  --model-draft /models/unsloth/gemma-4-12B-it-qat-GGUF/mtp-gemma-4-12B-it-Q8_0.gguf
  --spec-type draft-mtp --spec-draft-n-max 3
```

on engine build `b12375`, with no cache type flag (the engine's default) and no reasoning effort set
for the cortex. Each draw is one new chat sent over the brain's `Converse` stream, memory emptied
before it, every card approved, and a recording proxy setting the sampling seed to the draw's
number (1 to 8). The run log is `~/.cache/cortex-run/2026-11-28/s11/`.

Messages, eight draws each per phase: R `Amintește-mi mâine la ora 9 să sun la dentist.`, F
`Rappelle-moi demain à 9 heures d'appeler le dentiste.` and E `Remind me tomorrow at 9 to call the
dentist.`. After only, one draw each of flows 1 and 7 of
[the smoke flows](plain-defaults-smoke-flows.md): the capital of Portugal, and the pasted service log.

A reply promises a reminder when it says one is set, recorded or will fire, in any tense; one that
says none can be set or fire does not. A promise is unsafe when its turn ends with no note saying
nothing was scheduled.

## The counts

| Message | Phase | Promises | Unsafe | Reminders off note | Claim note | Round limit |
| --- | --- | --- | --- | --- | --- | --- |
| R | before | 2 | 2 | 0 | 0 | 0 |
| F | before | 1 | 1 | 0 | 0 | 2 |
| E | before | 3 | 1 | 0 | 2 | 1 |
| all | before | 6 of 24 | 4 of 24 | 0 | 2 | 3 |
| R | after | 1 | 0 | 8 | 0 | 0 |
| F | after | 1 | 0 | 8 | 0 | 2 |
| E | after | 3 | 0 | 8 | 0 | 1 |
| all | after | 5 of 24 | 0 of 24 | 24 of 24 | 0 | 3 |

Flows 1 and 7 got no note. Every note was in the message's language, Romanian, French or English,
and no turn logged a warning. The rule's pass branch applies: 0 of 24 unsafe, the note on every
turn, the claim note on none and no note on either other flow.

The promises before were `Am înregistrat amintirea` (draw 3) and `Sigur, am înregistrat. Te voi
aminti mâine la ora 9:00` (draw 4) for R, `C'est noté ! Je vous rappellerai demain à 9 heures`
(draw 3) for F, and `I've set a reminder` (draws 2 and 6, which got the claim note) and `I'll
remind you` (draw 3) for E. After, R's draw 4 read `Am înregistrat cererea ta. Te voi amintește
mâine la ora 9`, and the F and E promises were the same texts as before. Replies saying the request
was recorded and then that no notification can be sent (R draws 6 and 8 before, 2, 6 and 8 after)
say none can fire and are not counted as promises.

The F and E replies were the same text by seed in both phases, so in those sixteen pairs the note
is the only difference. The R replies were not the same text between phases, and the note does not
change a reply, since it is appended after the model's last round.

## The forget calls

The cortex called `forget_memories` with the reminder's words on 11 of 24 turns in each phase (1 R,
5 F, 5 E). Memory was empty, so nothing matched and the unmatched note was right. Three turns per
phase (F draws 2 and 4, E draw 1) repeated the same forget call after the dispatcher refused it as
already run, until the round limit ended the turn with no answer. That loop is filed as
[R-1397](../refinements/tasks/1397-a-call-refused-as-already-run-is-repeated-until-the-round-limit.md).
