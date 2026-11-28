# Readings: smoke flows on plain compose defaults

Fourteen flows a person types, each drawn three times on a brain built from the tree of 2026-11-28,
after the changes of that night: each round's thought sent back to the engine by default
(`CORTEX_REPLY_RESEND_TRACE`), no thought in a handoff record, the note when a later result stops
memory storing a turn, and the closing note language pick that reads French for a lone `ce` and
leaves quoted words out. The defects found are filed as tasks; nothing was changed in this pass.

## The rig

**2026-11-28.** Compose project `cortexn33`, the brain image built from the tree, the model host
from its existing image with the tree's model manager and core bound over its packages, and a
recording proxy between the brain and each tier. The model host started the cortex as:

```
llama-server --model /models/unsloth/gemma-4-12B-it-qat-GGUF/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf
  --host 0.0.0.0 --port 8080 -ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram 8192
  --model-draft /models/unsloth/gemma-4-12B-it-qat-GGUF/mtp-gemma-4-12B-it-Q8_0.gguf
  --spec-type draft-mtp --spec-draft-n-max 3
```

on engine build `b12375-9d25e0014`, text only, since `CORTEX_MODEL_FILE_CORTEX_MMPROJ` is empty by
default. Each draw is one new chat sent over the brain's `Converse` stream, the call the overlay
sends, with every card approved, the memory table emptied before it and the proxy setting the
sampling seed to the draw's number (1, 2, 3). The brain resolved `resend_trace` to true with the
setting unset.

- **Phase A**, plain defaults: every optional feature off. `CORTEX_SCHEDULE_BACKEND` is `none`,
  escalation is off, so the cortex is offered one tool, `forget_memories`.
- **Phase B**, the two features its flows need and nothing else: `CORTEX_SCHEDULE_BACKEND=redis`
  (zone `UTC`, the default) and escalation to the deep tier through the model host, with
  `CORTEX_MODEL_FILE_BRAIN=unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf` and
  `CORTEX_SWAP_BRAIN_VRAM_MIB=16991`. The cortex is offered seven tools.

The flows were written before the first draw, and flows 9, B4 and B5 before their own
first draws, each for a reason the section on it gives. The run log is
`~/.cache/cortex-run/2026-11-28/f1/`.

## The flows

| Flow | Message | Right outcome | Right |
| --- | --- | --- | --- |
| 1 | `What is the capital of Portugal, and roughly how many people live there?` | Lisbon, no tool, no error | 3 of 3 |
| 2 | `Remember that my bike lock code is 3917.`, then `What is my bike lock code?` in the same chat | 3917 | 3 of 3 |
| 9 | the same two messages, the second in a new chat | 3917, from memory | 3 of 3 |
| 3 | `Amintește-mi mâine la ora 9 să sun la dentist.` (phase A) | no claim that a reminder was set | 0 of 3 |
| 4 | `Rappelle-moi demain à 9 heures d'appeler le dentiste.` (phase A) | the same | 2 of 3 |
| 5 | `Remember that my bike is blue, then write me a two line poem about it.` | the fact noted and a poem | 3 of 3 |
| 6 | a picture (red, green and blue thirds) and `What colours are in this picture, from left to right?` | refused as a picture the model cannot see, or the colours | 3 of 3 |
| 7 | a pasted service log of 5,097 characters ending `Why did this service crash?` | the heap error line | 3 of 3 |
| 8 | `שלום! 🙂 מה השעה בטוקיו כשבתל אביב 12:00? 🌏🕛` | 19:00, since Tokyo is seven hours ahead of Tel Aviv on that date | 0 of 3 |
| B1 | flow 3's message (phase B) | one `schedule_task` call, a Romanian reply | 3 of 3 |
| B2 | flow 4's message (phase B) | the same in French | 3 of 3 |
| B4 | `List my reminders, then write me a two line poem about Monday mornings.` | a `list_scheduled` call, then the list and a poem | 3 of 3 |
| B3 | `Hand this to the deep model with your escalate tool: explain in about 60 words why the sky is blue.` | the deep tier answers and the cortex is served again | 3 of 3 |
| B5 | flow 8's message (phase B) | 19:00 | 3 of 3 |

## 1, 2, 5, 7 and 9: plain turns

Every reply of flows 1, 2, 5, 7 and 9 was right, none called a tool, and each stored its
exchange; no turn of flows 1, 2, 5 and 7 logged a warning, and flow 9's lines were not read. Flow 9 was added because flow 2's chat history already holds the code,
so only a new chat reads it from memory. Flow 5 is not the tool then reply shape on these
defaults, since the exchange is stored with no call and no tool to remember exists, so B4 draws
that shape. Flow 7's replies each named the `OutOfMemoryError` line, its time and the heap
warning one second before it.

## 3 and 4. A reminder with reminders off

All three Romanian replies said the reminder would fire: `Te voi amintește mâine la ora 9`,
`Sigur, am înregistrat amintirea. Te voi minte mâine la ora 9` (where `minte` means "lie") and
`Voi reține să te reamintesc mâine la ora 9:00`. None was given the note for a reply that claims a
reminder no call made, because these are a promise in the future tense or `am înregistrat`, which
that reader does not read. The first was given the Romanian note that the exchange is stored across
chats, since it said it would remember this "for our conversation tomorrow".

Two French replies said no reminder can be set and suggested the phone's own app. In the third
the thought planned a `set_reminder` tool that was not offered, called `forget_memories` with
`appeler le dentiste` and then `demain à 9h00`, and asked for tomorrow's date so that it could set
the reminder. Memory was empty, so nothing matched, the French unmatched note was right, and the
turn was not stored. Both forms now get the reminders off note, drawn in
[its readings](reminders-off-note.md).

## 6. A picture on a text only cortex

Each draw ended with the error `attachment_refused` (`the model now serving cannot read
pictures`) after one `GET /props` to the cortex and no chat request, with nothing stored and one
warning line logged.

## 8. A right to left message with emoji

The Hebrew and the emoji came back intact in every reply. Every reply said 18:00, a difference of
six hours that holds while Israel is on summer time; one added that in winter it would be 19:00.
The cortex request held no date: the only date a turn sends is in the `schedule_task`
description, which these defaults do not offer. The cortex in flow 4's third draw also wrote that
it did not know today's date. Flow B5 separates the two causes.

## B1, B2 and B4: reminders on

Every Romanian and French draw called `schedule_task` once, due 09:00 UTC the next day, and replied
in the message's language: `Am setat amintirea pentru mâine la ora 09:00.` and `C'est fait ! Je
vous rappellerai demain à 9h00 d'appeler le dentiste.` The three Romanian items read `Să sun la
dentist`, `Sun la dentist` and `Suna la dentist`, the last without its `ă` ([R-1057](../refinements/tasks/1057-a-romanian-reminder-reply-holds-a-broken-word.md) holds that
defect). The step that cancelled each draw's items failed, so French draws 2 and 3 were told the
item was already scheduled, and every B4 draw listed the four items stored.

Each B4 turn listed the four items and then wrote the poem. Every final round wrote a thought, and
every final request sent the first round's thought back with its tool call (1 of 1 in each draw).

## B3. A handoff to the deep tier and back

Every draw called `escalate_to_brain` once. The model host stopped the cortex, started the deep
tier, stopped it after the answer and started the cortex again, which was serving at the end of
each draw. Each reply said the request was handed over and then gave the deep tier's answer, two
to four sentences on Rayleigh scattering, and each turn stored two rows: the cortex's exchange
naming the handoff, and the deep tier's answer. The deep tier's request held the cortex's tool
call message with no `reasoning_content`, and after the third draw Redis held no `cortex:handoff`
key, and none of the three stored messages holding an answer had a thought. The highest card reading during phase B was 18,625 MiB,
the other apps' 2,668 MiB included. No turn logged a warning.

## B5. The right to left message with the date offered

Written after flow 8 and before its first draw, to separate a request with no date from a model
that ignores a date it has: flow 8's message on the phase B stack, whose `schedule_task`
description names the current date-time. All three replies said 19:00, two of them naming winter
time, so
the missing date explains flow 8; it is filed as [R-1396](../refinements/tasks/1396-with-reminders-off-the-cortex-is-given-no-date.md).
