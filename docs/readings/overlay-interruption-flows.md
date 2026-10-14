# Readings: a turn interrupted from the overlay, on the Linux shell

What the overlay, the session store and the next turn did when a person interrupted a turn in ways
[overlay-turn-flows.md](overlay-turn-flows.md), [delegation-overlay.md](delegation-overlay.md) and
[the overlay's view of a handoff](model-swap.md#the-overlays-view-of-a-handoff) did not cover: a new
chat or a second message while a reply streams, hiding the panel mid-stream, Stop or a new chat
while an approval card waits, Stop while the deep model loads, and Stop while a tool listing hangs.
The procedure is the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless).

## The rig

**2026-10-15**, the debug shell of the tree loading the overlay from Vite, on `Xvfb`, driven with
`xdotool`, frames grabbed with `ffmpeg` twice a second. The stack is that night's shared test
stack: gemma 12B as the cortex on the GPU, escalation on with gemma 31B as the deep model at a
16384 context, Postgres and the CPU embedder, the file sidecar, `CORTEX_TOOLS_ON_UNAVAILABLE=skip`
and `CORTEX_TOOLS_GATED='["read_text_file"]'`. Stored chats were read from the session lists in
Redis, tool calls from the brain's audit lines, and tier states from `GET /models/{model}` on the
model host once a second. SM clock during the flows: 0.55 to 0.59 of `clocks.max.sm`.

## A new chat while a reply streams

`Ctrl+N` 20 s into a 600 word essay, while its text streamed. The panel showed the empty new chat
at the next frame, and the model host logged `cancel task` for the essay's generation. The old chat
stored the essay question and no reply, as a stopped turn does. "Name two rivers in Romania, one
line." in the new chat was answered and stored in that chat alone.

## A second message while the first streams

"What is the capital of Peru?" typed and sent with Enter 14 s into a 400 word story. Enter did
nothing: the words stayed in the composer under the streaming reply, and the store holds only the
story's question and reply. When the story ended the send button lit with the words still in the
field, and nothing was sent until a second Enter.

## Hiding the panel mid-stream

The summon chord over the panel, 20 s into the same story, hid the whole window: no orb, as the
`toggle` action documents ("a running turn going on out of sight until it ends or asks"). The
chord 9 s later showed the panel with the reply further on and still streaming, and it ended in
place. The turn was never cut.

## A read that needs approval, in a turn that listed files

With `read_text_file` in `CORTEX_TOOLS_GATED`, "Read choir-rota.txt in my files and tell me who
sings in week 2." showed no card: the cortex called `list_allowed_directories` and `search_files`
first, whose results are untrusted, so the read was refused with the `BLOCKED` text that a turn
which read untrusted content runs no action needing approval. The reply said the file "contains
information from an untrusted source". A tool added to that list is treated as outbound, which is
the taint rule of [ADR-0013](../adr/ADR-0013-untrusted-content.md), so the escalation card is the
one used below.

## Stop, or a new chat, while a card waits

1. **Stop at the card.** The handoff prompt of `just rpc-handoff` showed the `escalate_to_brain`
   card; Stop closed the card and the turn, and the audit line read `DECLINED`. The store holds the
   question and no reply.
2. **The next turn raised the card again.** "What colour is a ripe lemon? One word." in the same
   chat brought back the `escalate_to_brain` card with the stopped request's brief, and no answer
   about the lemon.
3. **A new chat at that card.** `Ctrl+N` with the card up showed the empty new chat and wrote a
   second `DECLINED` audit line. `Ctrl+Down` back to the old chat showed the two questions with no
   reply under either, and nothing about the two declines.
4. **A third question raised it a third time.** "What is 2 plus 2?" brought back the same card.
   Approved this time, the cortex wrote one reply to all three questions, "Yellow. 2 + 2 = 4. I am
   now handing off your request ...", stored as the 2 plus 2 turn's reply.

Every stopped or abandoned turn stores its question with no reply and none of its runs
([ADR-0011](../adr/ADR-0011-body-v1.md) decision 1), so the next turn's model reads a request
nobody answered. A stopped action was taken up again here, and a stopped essay was not in
[the first baseline](#the-first-baseline). Filed as
[R-863](../refinements/tasks/863-a-request-stopped-at-its-card-comes-back-in-the-next-turn.md),
with the rows below.

## Stop while the deep model loads

The card above approved, then Stop 8 s later, while the chip read "loading the deep model; this
takes a few minutes". The model host had stopped the cortex and started the deep model; within a
second of the Stop it stopped the deep model and started the cortex again, and the brain logged
`a handoff ended failed reason="the turn was torn down before the handoff finished"`. The reply
kept the cortex's hand-over sentence with no note, and the store holds that sentence as the reply,
with the `escalate_to_brain` run. The link dot read amber while the cortex loaded and green after.
"What is 3 plus 3?" then got "3 + 3 = 6." with no new card.

## Stop while a tool listing hangs

The file sidecar frozen with `docker pause`, then "List the files in my files folder." in a new
chat. No tool row appeared: the turn waited on the listing at its start. Stop after 18 s ended it,
and the store holds the question only. The sidecar was thawed 2 s after the Stop; its child then
answered the cancelled session's `initialize`, and `supergateway` exited on
`No connection established for request ID: 0`. The container restarted, ran `npm install` again and
listened 7 s after the thaw. The same request sent 3 s after the thaw found it down
(`tool sidecar unavailable; serving without it`), and the reply read "I don't have the ability to
list the files in your folder", while the status line named the server. Filed as
[R-864](../refinements/tasks/864-a-cancelled-call-takes-the-file-sidecar-down.md).

## Rows for the stopped request

Written before any baseline is drawn, for R-863. Each row is a fresh chat on this stack.

- **Row K (card).** Turn 1 is the `just rpc-handoff` prompt; press Stop while its card waits.
  Turn 2 is "What colour is a ripe lemon? One word." A row fails when turn 2 calls
  `escalate_to_brain` (its audit line) or its reply speaks to the sum of odd numbers.
- **Row T (text).** Turn 1 is "Write a 600 word essay about the history of the bicycle."; press
  Stop once its text streams. Turn 2 is "Name two rivers in Romania, one line." A row fails when
  turn 2's reply goes on with the essay or mentions bicycles.
- **Row R (repeat).** Row K, then turn 3 "Please hand that sum question to the deep model now." A
  row fails when turn 3 does not call `escalate_to_brain`.

The rule: 5 baseline rows of K and of T on the shipped build. The defect reproduces when 3 or more
K rows fail. A candidate passes when 0 of 5 K rows and 0 of 5 T rows fail and 4 or more of 5 R rows
pass; any other result leaves the shipped behaviour as it is.

### The first baseline

Drawn the same night on the overlay, one fresh chat per row, Stop 22 s after turn 1 was sent
(every K row's card was up: each wrote a `DECLINED` line), turn 2 read 28 s after it was sent.

| Row | Fails | Passes | Not settled at 28 s |
| --- | --- | --- | --- |
| K | 1: the card came back | 2: "Yellow" | 2: still thinking, no card and no reply |
| T | 0 | 5: "The Danube and the Olt ..." | 0 |

So the defect stays under the rule's 3 of 5 on this baseline, and no candidate is run. A stopped
essay is never taken up again; a stopped action is, in 1 of 3 settled rows here and in both turns
of the flow above. **The next rows**, written before they are drawn: 5 K rows in which turn 2 is
read once it stores a reply or shows a card, waiting up to 120 s, under the same rule.

Method: the drivers, frames and logs are in the run's scratch directory, not in the tree.
