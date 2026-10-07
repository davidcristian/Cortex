# Readings: turns that end early, and memory across chats, on the Linux shell

What the overlay, the shell and the brain did when a person stopped a turn, when the brain was down
or died during a reply, and when a later chat asked about an earlier one. Cited by
[ADR-0011](../adr/ADR-0011-body-v1.md) and [the embedding module](../modules/brain-embedding.md).
The procedure is the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless).

## The rig

**2026-10-07**, a debug build of the shell from the tree with the overlay embedded
(`tauri/custom-protocol`), WebKitGTK drawing in software on an `Xvfb` display, against a stack
built from the tree on the 24 GB card: the shipped cortex alone, with
`docker/docker-compose.memory.yml` adding Postgres and the CPU embedder. Every key and click came
from `xdotool` and every frame from `ffmpeg -f x11grab`. The card's SM clock read 0.58 of
`clocks.max.sm` and the cortex decoded at a steady rate through every turn, so the figures below
are given as fractions of one turn's own generation.

## Stop

The shell here had no `stop_turn` yet: the overlay's Stop muted the reply and left its RPC
running. [With the abort](#with-the-abort) is the same flow once the Stop dropped the RPC.

- **The stopped generation runs on.** A turn asked for a long essay was stopped with the button
  57% of the way through its generation time. The model went on to the end of that generation, and
  the brain stored the whole reply, while the overlay kept the text it had shown.
- **The next turn waits for it.** A question sent 1.2 s after the Stop, in the same chat, reached
  the model only when the stopped generation ended, 0.75 s after its last token.
- **The store interleaves the two turns.** The follow-up started before the stopped reply was
  stored, so the chat's list held the essay question, the follow-up, the essay and the follow-up's
  answer, in that order. A third question in the chat was answered from the whole essay, which the
  overlay had shown only in part.
- **The caret after a press.** Clicking the button left focus on it. The follow-up typed next went
  nowhere, its `?` opened the console's Chords tab, and Enter or Space would have pressed the
  button. After the fix the field takes the caret back after either press, and text typed after a
  click on Send and after one on Stop went into it.
- **A stop before any text** left an empty reply bubble under the `Thoughts` disclosure.

## With the abort

**2026-10-07**, the same rig with the shell's `stop_turn` built in and the brain running a
session's turns one at a time. The SM clock read 0.49 to 0.63 of `clocks.max.sm` while the cortex
decoded. Times in the brain's store and the model host's log come from one clock; the driver's
clicks were stamped on the host's, which differed from it by 0.12 to 0.27 s just after the runs.

- **The generation ends at the Stop.** An essay was stopped twice, once while the cortex still
  thought (over 600 tokens in) and once while its text streamed (over 1500 tokens in). Each time the
  model host logged `cancel task` within a fifth of a second of the click and freed its slot
  13 ms and 14 ms later. The brain logged no error.
- **The next question does not wait.** A follow-up sent 1.5 s after the click stored its question
  1.7 s and 2.5 s after the slot was freed, and its first model call found the slot free.
- **The chat keeps the order the person saw.** Both chats held the essay question, the follow-up
  and its answer, in that order, with no part of the stopped essay: a cancelled turn stores no
  reply. The overlay showed the essay question, the stopped reply (empty in the first run, part of
  the essay in the second), the follow-up and its answer.
- **A stopped reply goes on writing.** In the second run the stopped bubble's text ended mid-word
  0.4 s after the click, had moved a section further on 14 s after it with the mist on its last
  word, and had settled by 88 s after it: the Stop kept the text received but not yet drawn, and
  the bubble drew it at the whisper front's pace
  ([R-816](../refinements/tasks/816-a-stopped-reply-goes-on-writing-and-is-not-kept.md)).
- **Two streams on one chat.** A script in the brain's container opened two `Converse` streams on
  one session, the second question sent 0.5 s after the first. The chat stored the first question,
  its reply, the second question and its reply, in that order, and the second reply named the
  oldest of the bridges the first one had listed.

## The brain down, and dying during a reply

- **Down at the send.** With the brain's container stopped, a question sent from an open panel
  ended in a red bubble reading `no reply within 5s`, and the dot went red. Here the dial to the
  stopped brain's port waited for the call deadline: a dead loopback port outside the ephemeral
  range is not refused on this machine. After `docker start` the dot went green at the next
  re-check with no summon, and the next question in the same chat was answered.
- **Killed during a reply.** `docker kill` of the brain while a reply streamed ended it with
  `Unknown: h2 protocol error: error reading a body from connection`, the dot amber and then red.
  Before the fix that error bubble replaced the reply and the paragraph already on screen
  disappeared, though the overlay's state still held it. After the fix the text that arrived stays
  above the error.

## Memory across chats

- **A short exchange** told in one chat ("my sister Ilona moved to Cluj and keeps bees there") was
  recalled in a new chat: asked which city and what she keeps, the cortex answered Cluj and bees.
- **A long exchange was never recorded.** Every exchange whose text came to more than 512 tokens
  failed its memory write: the embedder logged `input (1064 tokens) is too large to process.
  increase the physical batch size (current batch size: 512)`, and the brain logged
  `memory write unavailable; this exchange was not recorded to memory`. The three essays asked
  before the change below were all lost this way. `llama-server` caps an embedding input at its
  micro-batch, whose default is 512 tokens, below the model's 2048-token context.
- **With `--batch-size 2048 --ubatch-size 2048`**, a 1562-token input embedded, an essay
  exchange of 1098 tokens was recorded, and a 2602-token input still failed with the same error at
  2048.

## The keyboard

- **The conversation.** With a reply taller than the window, `Page_Up` in the field changed
  nothing. Seven presses of `Tab` from the field went to the send button, the hint strip's console
  and Chords buttons and the header's buttons, and never to the conversation, so it could not be
  scrolled without a pointer.
- **The composer at its cap.** Eleven lines entered with `Shift+Enter` grew the field to its
  ceiling, after which it scrolled its own window with the cut line faded, and `Page_Up` moved the
  caret within the draft.

Method: `measurements/linux-shell-flows-2026-10-07/`, with the scripts that ran the shell and the
stack, frames in `shots/` (`B-*` and `C-*` the stops, `D-*` to `F-*` the outage, `G-*` the
recall, `H-*` and `I-*` the fixed build, `K-*` and `L-*` the keyboard), the brain's and the model
host's logs. The abort's runs are in `measurements/stop-abort-2026-10-07/`: `stopflow.sh`,
`twostreams.py`, the frames (`B-*` the stop while thinking, `C-*` the stop during text), the
stored chats, the card's samples and both logs.
