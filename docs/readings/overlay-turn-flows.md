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
host's logs.
