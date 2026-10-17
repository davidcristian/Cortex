# Readings: turns from several chats at once, on the Linux shell

What the brain, the session store and the overlay did when turns from several chats, or two
turns from one chat, were in flight together: two chats at once, one chat sent to twice from two
clients, a Stop or a dropped stream in one chat while another streams, an overlay chat beside a
second `Converse` client, two handoffs to the deep model requested close together beside a plain
chat, a scheduled reminder firing while a turn streams, and a memory forget in one chat while
another chat's turn recalls. Earlier flows interrupted one chat at a time
([interruption flows](overlay-interruption-flows.md)); these put two clients on the brain at once.

## The rig

**2026-10-17**, the debug shell of 2026-10-13 (newer than every Rust and proto change in the
tree) loading the overlay from Vite, on `Xvfb`, driven with `xdotool`, frames grabbed with
`ffmpeg`, as [the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless)
describes. The stack is that night's shared test stack: gemma 12B as the cortex on the GPU with
`--parallel 1`, escalation on with gemma 31B as the deep model, Postgres and
the CPU embedder, the file sidecar. The second client is a small script inside the brain container
that sends one `UserTurn` over `Converse`, approves every `ConfirmRequest`, and can send `Cancel`
or cancel the call after a set delay. Stored chats were read from the session lists in Redis
(`cortex:session:<id>:messages` and the `cortex:sessions` index), tier states from
`GET /models/{model}` on the model host once a second. SM clock during the handoff flow: 0.51 to 0.67 of
`clocks.max.sm`. For the reminder and forget flows the brain ran with
`CORTEX_SCHEDULE_BACKEND=redis` (5 s schedule poll, no body endpoint, so a fired reminder waits
for the overlay to pull it) and `CORTEX_MEMORY_ON_TAINTED=record`.

The right behaviour was written before each run: every reply reaches the chat that asked, each
chat stores its own question and reply once and in order, a turn waiting for the card waits and
then runs, and no turn is left running after its stream ends.

## Two chats at once

"Write four sentences about rivers." and "... about mountains." sent on two streams in the same
instant. **As expected.** The cortex serves one generation at a time, so the second turn's first
event came only after the first turn's text had ended; both replies reached their own streams and
each chat stored one question and one reply. The waiting stream received no event while it
waited, since the heartbeat period is 30 s; see below.

## One chat sent to twice

"Name a colour, one word." and, 50 ms later on a second stream with the same session id, "Which
colour did you just name? One word." **As expected.** The second turn started only after the first
had stored its reply (`SessionTurnLocks`), its reasoning quoted the first exchange, and it answered
"Blue" again. The chat stored the four messages in order, each pair under its own turn id.

The same with the overlay as the second sender: the second client sent "Write eight sentences
about glaciers." on the overlay's open chat, and 1.5 s later "Name a colour, one word." was typed
in the overlay and sent. **As expected.** The overlay's chip read "waiting for this chat's previous
message to finish" (the `queued` wait `CHAT_AHEAD`, sent as a status at once) until the glacier
reply was stored, and then the reply "Green" streamed. The chat stored both exchanges in order.

## Stop or a dropped stream in one chat while another streams

Chat Y sent "Write five sentences about the sea."; 0.5 s later chat X sent "... about deserts."
on its own stream, so X waited behind Y for the card; 3 s later X's client sent `Cancel`.
**As expected.** X's turn ended with no further event and Y's reply streamed to the end and was
stored. X stored the question and no reply, as a stopped turn does. A new turn in X ("Name a
planet, one word.") ran as soon as Y's generation ended and was stored after the stopped question.
A `Cancel` ends the turn and leaves the stream open, as `ConverseStream` states, so the first
client written for this flow, which waited for a `TurnComplete` after its `Cancel`, waited until
its own timeout; a client that ends its input after the `Cancel` sees the stream end at once.

The same with X's client cancelling the whole call in place of `Cancel`: the call ended
`CANCELLED`, Y was untouched, X stored the question alone, and X's next turn ran after Y's.

## An overlay chat beside a second client

`Ctrl+N`, then "Write five sentences about volcanoes." typed in the overlay and sent with Enter;
0.3 s later the second client sent "... about islands." on chat `s8-o1`. **As expected.** The
overlay streamed the volcano reply only, with its link dot green throughout, and returned to the
idle composer; the second client's turn waited for the overlay's generation and then streamed the
island reply. Each chat stored only its own exchange.

## Two handoffs close together beside a plain chat

Chat H1 sent "Hand this to the deep model, please: in two sentences, why are there infinitely many
primes?"; 2 s later chat H2 asked the same for the square root of two; 1 s later chat Z sent "Name
a fruit, one word."; and once H1's swap was under way chat W sent "Name a river, one word.". The
right behaviour, from [ADR-0030](../adr/ADR-0030-brain-handoff.md) decisions 5 and 6: one handoff
runs, the other is refused with a note that is streamed and not stored, and a plain turn waits
for the cortex to come back.

**As expected.** Both cortex turns called `escalate_to_brain`, both confirm cards were approved and
both tool outcomes were `ok`. H1's turn took the swap claim; H2's hand-over sentence was followed by
the streamed note "A handoff to the deep model is already running, so this one was not started.",
and H2 stored the question and its hand-over sentence only, which the replay text of
[the lost-reply readings](handoff-reply-not-kept.md) then describes as a handoff with no stored
reply. Z was answered by the cortex before the swap began. W's first event was `swapping`
"waiting for another request's handoff to the deep model to finish", repeated by the 30 s
heartbeat; it was answered once H1 had finished and the cortex was `ready` again. H1 streamed the
drain, load, deep work and restore states and stored the question, the hand-over sentence and the
deep reply. Nothing was stored twice and every stream ended.

## A reminder firing while a turn streams

The right behaviour, written first: the reminder becomes deliverable within one poll of its due
minute, the streaming reply goes on with no gap or error and is stored once in its own chat, no
reminder text enters any chat, the card shows on the overlay's next empty chat, and dismissing it
acks it.

Chat `s9-r2` asked "Remind me at 06:03 today to stretch my legs." (`schedule_task`, ok). At
06:02:52.9, 7 s before the due minute, "Write twelve sentences about the history of ships." was
sent from a new overlay chat. **As expected.** The reminder became deliverable at 06:03:03.9 while
the reply streamed (the brain stored it at 06:03:04.0); frames at 06:03:01, 06:03:07 and 06:03:13
show the reply growing with no gap and the link dot green, and it was stored once. No chat stored
the reminder's text. The ship chat did not show the card, since the reminder stack shows only on an
empty chat; after a hide and summon, `Ctrl+N` showed "stretch my legs", "1m ago", and its check
mark acked it: the deliverable set was empty and the one-time record gone.

## A forget in one chat while another chat recalls

The right behaviour, written first: no crash; a recall that began before the forget may use the
forgotten row; once the forget is confirmed, no turn recalls the forgotten fact; the store holds no
row derived from it.

The file sidecar's root held `shed.txt`, "The shed's padlock code is 4417.". Chat `s9-f0` asked
"Read the file shed.txt and tell me what it says.", which stored one tainted row. Then chat `s9-fa`
sent "Forget every remembered exchange that came from untrusted content." and 0.3 s later chat
`s9-fb` asked "What is the shed's padlock code?". **Not as expected.** The forget card was
approved and the tool deleted the row at 06:05:52.6; `s9-fb`, whose recall had read the row before
the delete, answered "The shed's padlock code is 4417.", which is allowed, but its own exchange was
then stored as a new tainted row at 06:05:57.1, after the delete. A new chat `s9-fc` asking the
same question at 06:06:00 recalled that row and answered "4417". Nothing crashed and every stream
ended.

A turn's memory record is stored only while the tainted memories that turn recalled still exist,
checked in the insert under a `FOR SHARE` lock, and `delete_tainted` repeats until a pass removes
nothing ([ADR-0019](../adr/ADR-0019-tainted-memory-recording.md) decision 9). Two `psql` sessions
on the `cortex_contract` database show why both halves are needed: a forget whose `DELETE` waited
on a record's share lock removed the recalled row but not the new one, which a second `DELETE`
removed, and a record that waited on the forget's `DELETE` inserted nothing.

Replayed at 06:34 on a brain built with that check, chats `s11-*`, the SM clock at 0.59 of
`clocks.max.sm` before the run. The forget deleted the row at 06:34:20.1; `s11-fb` again answered "4417"
from its recall and logged "a memory this turn recalled was forgotten; this exchange was not
recorded to memory", and no row was stored after the delete. `s11-fc` read `shed.txt` itself, which
was still in the root, and answered from the file. A second replay at 06:35 (`s11b-*`) removed
`shed.txt` after the seed: the forget deleted the row at 06:35:15.1, `s11b-fb` answered "4417" and
was not recorded, and `s11b-fc` found no code. As expected both times.

## Stop or a dropped stream while a turn waits for its own chat

The right behaviour, written first: the waiting turn ends with nothing stored; the turn ahead and a
later queued turn run in order; a turn sent after the queue empties gets no `queued` status; the
status a turn shows says what it waits on now.

On one session id at 06:48, chat `s12-q-cancel`: A "Write eight sentences about rivers, one per
line.", 0.5 s later B "Name one colour." on a second stream, cancelled 2 s later while queued,
4 s later C "Name one fruit.", and D "Name one animal." after all three ended. **As expected**
for the lock: B got the `queued` status at once and ended at its `Cancel` with no further event, C
got the `queued` status and answered after A, D got no `queued` status, and the chat stored A, C
and D in order with nothing of B's. The same at 06:49 with B's call cancelled in place of a
`Cancel` (`s12-q-drop`) gave the same result. **Not as expected** for the status: A's reply ended
2.0 s into C's wait in the first run and 5.5 s in the second, and C's first `thinking` status came
6.2 s and 4.0 s after that, while D, with nothing ahead, took 4.3 s and 3.6 s to its first status.
For those seconds C's last status still said "waiting for this chat's previous message to finish",
since closing the wait sends nothing. The SM clock read 0.59 of `clocks.max.sm` just after the
two runs.

## A forget's delete against a record that recalled two rows

Three `psql` sessions on the `cortexn7` Postgres's `cortex_contract` database at 06:51: tainted
rows `r2`, `x`, `r1` in heap order and 5,000 untainted rows, so the record's `FOR SHARE` subquery
takes an index scan (id order) and the tainted `DELETE` a sequential scan (heap order). A third
session held `x` for 2 s, which stopped the `DELETE` just after it locked `r2`, as a long scan
would; the record recalling `['r1', 'r2']` then locked `r1` and waited on `r2`. When `x` was
released the `DELETE` failed with `deadlock detected`, so nothing was deleted and the derived row
was stored.

## Defects

- **A wait behind another chat is not named.** A turn waiting for another chat's generation is
  inside its own `thinking` wait, because the queue is llama-server's single slot, so its heartbeat
  says "working out the reply" while nothing of its own is being worked out, and the stream is
  silent until the first heartbeat 30 s in. Only a second client reaches this today, since the
  overlay keeps one chat in flight. Filed as
  [R-894](../refinements/tasks/894-name-a-turn-waiting-behind-another-chat.md).
- **A forget keeps a row a turn in flight records**, above, with the replay under the
  recalled-memory check after it.
- **A queued status stays after the turn ahead ends**, until the waiting turn's first reasoning.
  Filed as [R-897](../refinements/tasks/897-a-queued-status-stays-after-the-turn-ahead-ends.md).
- **A forget deadlocks with a record that recalled two tainted rows**, and the whole forget rolls
  back. Filed as
  [R-896](../refinements/tasks/896-a-forget-deadlocks-with-a-record-that-recalled-two-tainted-rows.md).

## Not run

Two overlay chats at once cannot be run: the overlay keeps one chat in flight, since `Ctrl+N` and a
second message stop the first ([interruption flows](overlay-interruption-flows.md)). A reminder
pushed to the shell while a turn streams was not run, because the shell's `BodyService` listens on
loopback only and the brain container cannot reach it.
