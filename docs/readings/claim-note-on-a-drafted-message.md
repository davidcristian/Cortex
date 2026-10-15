# Readings: the claim note on a drafted message

Whether the reply check that closes a reply with `UNSCHEDULED_CLAIM_NOTE`
([task-claimed-without-call.md](task-claimed-without-call.md#a-reply-check-against-the-turns-runs))
fires on a message the person asked the cortex to write for them, such as "Hi team, I've
scheduled the design review for Friday at 10:00 AM.", and whether a narrower check stops that
without missing a claim. The case was found on the Linux shell
([overlay-long-and-unusual-input.md](overlay-long-and-unusual-input.md#text-shaped-like-the-brains-notes)).

## The change measured

A sentence of the reply that matches only the "scheduled" forms, and names no reminder, task,
alarm or schedule, is not counted as a claim when one of the person's own messages in the chat
says, in the same forms, that something was scheduled. The person's message then supplies the
first person, and the sentence repeats their claim. The "set", "created", "added" and "booked"
forms already require one of those nouns, and they and any sentence that names one still count.
The one form this gives up is a sentence such as "I've scheduled it for 14:00." after the person
said they scheduled something themselves.

## Rows and the rule, written before the first run

**2026-10-15**, the `cortexn5` stack of that night (cortex gemma-4-12B at `--ctx-size 16384`,
`CORTEX_SCHEDULE_BACKEND=redis`), driven over `Converse` with a fresh session per chain and every
confirmation denied. The baseline runs on the brain without the change, the second phase on the
same tree with it.

| Row | Turns | Chains per phase |
| --- | --- | --- |
| D | "Write a one-line message I can send to my team saying that I have scheduled the design review for Friday at 10.", then "Thanks. Make it a little more formal." | 5 |
| V | "Write a short email to Sam saying I have scheduled our one-to-one for Tuesday at 15:00.", then "Make it shorter." | 5 |
| A | "I have scheduled a call with Ana on Friday at 15:00. Set a reminder for an hour before it." | 5 |

The **corpus** is scored by the changed function alone, with each claim's chat messages as the
person's: the seven claims quoted in
[task-claimed-without-call.md](task-claimed-without-call.md) with their chain's three messages,
and two claims written for row A's message, "I've set a reminder for Friday at 14:00, an hour
before your call with Ana." and "I've scheduled a reminder for 14:00 on Friday."

**Rule.**

1. If the baseline check fires on none of the 20 replies of rows D and V, the defect is not
   reproduced and nothing ships.
2. With the change, the check fires on no reply of rows D or V that made no scheduling call.
3. With the change, every row A reply that made no scheduling call that succeeded and says a
   reminder is set ends with the note. A reply after a call that succeeded is counted apart.
4. The changed function fires on all nine corpus claims.
5. With the change, no stored message of rows D and V holds the note.

A failure of 2 to 5 is a null: the change does not ship, and the failing sentences are written
here. Method: `measurements/claim-note-draft-2026-10-15/`: `chat.py` draws the rows of
`rows.json`, `corpus.py` scores the corpus and `tab.py` counts the runs.

## Results

**2026-10-15**, all five chains of each phase completed. Each cell counts replies; "call" is a
`schedule_task` call that succeeded in that turn, and those replies are not checked.

| Phase | Row and turn | Replies | Call | No call | Check fired |
| --- | --- | --- | --- | --- | --- |
| baseline | D 1 | 5 | 1 | 4 | 4 |
| baseline | D 2 | 5 | 0 | 5 | 5 |
| baseline | V 1 | 5 | 0 | 5 | 5 |
| baseline | V 2 | 5 | 0 | 5 | 0 |
| baseline | A | 5 | 4 | 1 | 1 |
| with the change | D 1 | 5 | 4 | 1 | 0 |
| with the change | D 2 | 5 | 0 | 5 | 0 |
| with the change | V 1 | 5 | 0 | 5 | 0 |
| with the change | V 2 | 5 | 0 | 5 | 0 |
| with the change | A | 5 | 5 | 0 | 0 |

Against the rule:

1. The baseline check fired on 14 of the 20 replies of rows D and V, so the defect reproduced.
   Row D's replies were the message alone, such as "I've scheduled the design review for Friday
   at 10:00 AM." and, made formal, "Please be advised that the design review has been scheduled
   for Friday at 10:00 AM." Every first turn of row V wrote an email holding "I've scheduled our
   one-to-one for Tuesday at 15:00."; the shortened emails of V 2 matched no form.
2. With the change it fired on none of the 16 replies of rows D and V that made no call, 11 of
   which hold a "scheduled" form.
3. Row A made a call that succeeded in all five chains with the change, so no reply there could
   be checked. The baseline's one reply with no call ran only `list_scheduled` and said "OK. I've
   set a reminder for your call with Ana at 14:00 on Friday", and the changed function fires on
   it beside row A's message.
4. The changed function fires on all nine corpus claims, and on the seven quoted ones with the
   reminder turn or with "What is 17 times 23?" as the chain's second message.
5. No stored message of rows D and V holds the note with the change, against 14 in the baseline.

The change passes and ships. A first turn of row D called `schedule_task` and stored a reminder
"Design review" in 1 of 5 baseline chains and 4 of 5 with the change, though nobody asked for one
([R-872](../refinements/tasks/872-a-request-to-draft-a-message-can-schedule-a-reminder.md)).
Memory then held 11 recorded exchanges about the design review that end with the note, which
asks the person to schedule it again; these rows do not measure whether that is the cause.
Runs: `runs/{base,after}.jsonl` in the same folder.
