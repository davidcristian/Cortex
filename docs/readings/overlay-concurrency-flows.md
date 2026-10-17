# Readings: turns from several chats at once, on the Linux shell

What the brain, the session store and the overlay did when turns from several chats, or two
turns from one chat, were in flight together: two chats at once, one chat sent to twice from two
clients, a Stop or a dropped stream in one chat while another streams, an overlay chat beside a
second `Converse` client, and two handoffs to the deep model requested close together beside a
plain chat. Earlier flows interrupted one chat at a time
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
`clocks.max.sm`.

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

## The one defect: a wait behind another chat is not named

A turn waiting for another chat's generation is inside its own `thinking` wait, because the queue
is llama-server's single slot, so its heartbeat says "working out the reply" while nothing of its
own is being worked out. A turn waiting for an earlier turn of its own chat holds no wait at all, so
its heartbeat is empty. In both cases the stream is silent until the first heartbeat 30 s in.
Filed as [R-894](../refinements/tasks/894-name-a-turn-waiting-behind-another-chat.md).

## Not run

A scheduled reminder firing while a turn streams and a memory forget in one chat while another
chat's turn recalls did not fit the slot's time. Two overlay chats at once cannot be run: the
overlay keeps one chat in flight, since `Ctrl+N` and a second message stop the first
([interruption flows](overlay-interruption-flows.md)).
