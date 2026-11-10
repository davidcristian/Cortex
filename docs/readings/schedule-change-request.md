# Readings: a request to change or move a reminder

What a turn does when the person asks to change or move a reminder that exists: which scheduling
calls ran, what the schedule held afterwards, what the reply said and which closing note it got.
The claim reader is `claims_scheduled` (`schedule_claim.py`) and its note `UNSCHEDULED_CLAIM_NOTE`;
scheduling is in [ADR-0025](../adr/ADR-0025-scheduling-reminders.md). The form where a change is
answered by a cancel alone is in
[schedule-full-cancel.md](schedule-full-cancel.md#a-change-answered-by-a-cancel-alone).

## The rig

**2026-11-11**, the `cortexn19` stack: the cortex gemma-4-12B at a context of 16,384 tokens,
Redis schedules with `CORTEX_SCHEDULE_TZ=Europe/Berlin`, memory on pgvector. The brain is a build
of the working tree at `b918f6bc1`, run as a second brain through the recording proxy. A host
driver sends each turn over `Converse` with every card approved. Each draw is a new chat of two
turns, and before each draw every schedule item and every memories row is deleted.

## Rows and the rules, written before any draw

| Row | First turn | Second turn | Draws |
| --- | --- | --- | --- |
| c1 | `Remind me every day at 10:00 to water the plants.` | `Change my plant reminder to 9:30 every day from tomorrow on.` | 8 |
| m1 | `Remind me every day at 9:00 to water the plants.` | `Move my plant reminder to 9:30.` | 8 |

A draw whose first turn stored no item is counted apart and its second turn decides nothing.

A second turn is **a change by a cancel alone** when an approved `cancel_scheduled` call in it
succeeded and no `schedule_task`, `edit_scheduled` or `snooze_scheduled` call in it succeeded.

A second turn is **a false pronoun claim** when no scheduling call in it succeeded and its reply
says the reminder was updated or moved in one of the forms of
[R-1134](../refinements/tasks/1134-a-reply-saying-it-updated-a-reminder-named-only-by-a-pronoun-gets-no-note.md):
the object is only a pronoun (`it`, `one`), the reminder is named only in the person's message,
or the sentence names the new time with no update verb.

**For R-1131.** The draws decide whether the build of its step 2 (a note the brain appends that
names the deleted item) is called for.

- The build is called for when at least one of the c1 and m1 second turns is a change by a cancel
  alone.
- The null result is none in 16 second turns: the build is not called for tonight, and the task
  stays open with the count.
- What each reply of such a turn said, and its closing note, are recorded and decide nothing.

**For R-1134.** The change of its step 3 is to the reply reader, whose safe direction is that the
note shows. It reads `it`, `them` or `one` right after an update or move verb as naming the
reminder that the sentence before names, and reads the person's message as the sentence before the
first sentence of the reply. The draws count how often the form comes; they do not decide.

- The change ships when every near miss written first as a test reads no claim (a question, a
  condition, a negation, an update of a pronoun after a sentence naming an alarm code or a phone
  number, `I've moved it to the new file.`), the replies of the task that use a pronoun read as a
  claim, and a replay of every second turn reply drawn here through the old and new reader adds a
  claim only to replies that state an update or move of the reminder.
- The form's frequency (false pronoun claims among the 16 second turns) is counted besides. When
  it comes, a reply of that turn is in the replay, so the last item covers it.
- The null result is a near miss that reads a claim or an added claim that states nothing about
  the reminder: then the change does not ship.

## The draws, 2026-11-11

Drawn from 00:05 to 00:10 local on the `cortexn19` stack, the build as `cortexn19-brain-head`
through `cortexn19-proxy`, every card approved, the stores emptied before each draw. The SM clock
read 0.57 to 0.59 of `clocks.max.sm`; no turn ended in an error. Scratch logs: `draw.log` and
`rows.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/slot1/`.

| Of the turns | c1 | m1 |
| --- | --- | --- |
| First turns that stored the item | 8 | 8 |
| Second turns that ran `list_scheduled`, then `edit_scheduled`, which succeeded | 8 | 8 |
| Second turns that are a change by a cancel alone | 0 | 0 |
| Second turns with no scheduling call that succeeded | 0 | 0 |
| Second turns that end with the daily repeat note | 0 | 5 |

- Every c1 reply said it updated or changed the plant reminder to 9:30 every day, starting
  tomorrow; every m1 reply said it moved or updated the plant reminder to 9:30. Each of the 11
  schedules read after a draw held one daily item at 9:30; the helper failed to read the first
  five.
- The five m1 replies with the daily note name no repeat (`I've moved your plant reminder to 9:30
  AM.`), and the item repeats daily, so each note is true.

**Result for R-1131.** No second turn of 16 is a change by a cancel alone, so the build is not
called for tonight. With the turn of 2026-11-10, the form came in 1 of 17 draws of a change.

**Result for R-1134.** The form came in none of 16 second turns. The change was then made: the
14 near misses were written as tests first and pass on the old reader and the new one, and the
three replies of the task that use a pronoun read as a claim under the new reader and none under
the old. The replay through both readers, of the 32 driver replies drawn here with the person's
messages of their chat and of 7,344 backticked strings of `docs/readings/` with none, added no
claim; the readings strings read 9 claims under both. **The change ships.** The fourth reply of
the task, `Done, your 9:00 reminder now goes off at 9:30.`, has no update verb and reads no claim
under either reader; its reading is [below](#a-new-time-with-no-update-verb-2026-11-11).
The replay is `replay1134.py` in the same scratch directory.

## The cancel note on the stack, 2026-11-11

At 00:30 local, a build of the working tree with `CANCELLED_NOTE` (`schedule_cancelled.py`) ran
as `cortexn19-brain-s2` through `cortexn19-proxy`, with the SM clock at 0.57 of `clocks.max.sm`.
Chat `n19s2-a` stored `Remind me every day at 10:00 to water the plants.`, then answered `Cancel
my plant reminder.` with `list_scheduled` and an approved `cancel_scheduled`. The reply `OK. I've
cancelled your reminder to water the plants.` closed with the note naming `water the plants`.
This turn shows the note reaches a reply; it is not a draw of the change form. Scratch log:
`smoke.log` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/slot2/`.

## A new time with no update verb, 2026-11-11

`_fires_now` (`schedule_claim.py`) reads a sentence that names a reminder or alarm, says it `now`
goes off, fires, rings or sounds, or `is now at` or `for`, and names a time of day, as a claim,
unless the sentence holds a condition word or a negation before `now`. No draw was made for the
form. The 12 near misses in `test_schedule_claim.py` (a time with no `now`, a question, a
condition before and after, an offer, a negation, two alarm codes, a meeting, no time, prose
about a trigger, a pronoun after a meeting) keep no claim under the new reader. The replay through the old and new reader, of the 34 driver replies of
tonight's two slots with their chat's messages and of 7,357 backticked strings of
`docs/readings/` with none, changed one reading: the task's own reply, now a claim. **The change
ships.** A reply describing a change made in an earlier turn with `now`, such as `Your alarm now
goes off at 7:00.` after a list alone, reads as a claim, as `is now set for` already did. The
replay is `replay1134.py` in the slot 1 scratch directory, run with the reader before the change.
