# Readings: a model swap under pressure, on the Linux shell

What the overlay, the session store and the next turn did when a handoff to the deep model met
pressure from outside the turn: card memory held by another process, Redis refusing writes at its
memory limit, and a new chat opened while the deep model loaded or while the cortex came back.
[The overlay's view of a handoff](model-swap.md#the-overlays-view-of-a-handoff) and
[Stop while the deep model loads](overlay-interruption-flows.md#stop-while-the-deep-model-loads)
cover the plain handoff and the kills. The procedure is the Linux section of
[the overlay runbook](../runbooks/body-overlay.md#the-tauri-app-on-linux-headless).

## The rig

**2026-10-16**, the debug shell loading the overlay from Vite, on `Xvfb`, driven with `xdotool`.
The stack is that night's shared test stack: gemma 12B as the cortex, escalation on with gemma 31B
as the deep model at a 16384 context, `CORTEX_SWAP_BRAIN_VRAM_MIB` unset (no fit check),
Redis with its append-only file, Postgres and the CPU embedder. Every handoff is the
`just rpc-handoff` prompt, its card approved by a click. Tier states are 1 s polls of
`GET /models/{model}` on the model host, card memory is `nvidia-smi` `memory.used`, and stored
chats are the session lists in Redis. SM clock during the flows: 0.58 of `clocks.max.sm` in most
samples, 0.43 to 0.68 over all of them.

## Card memory held by another process

A side container from the `cortex-model-host` image ran `llama-server` with the 12B model at
`-ngl 99` on its own port and took 7801 MiB, which left the model host reporting 5503 MiB free with
the cortex loaded. The deep model needs about 19800 MiB above the idle floor, more than the
cortex's memory plus that free figure.

- **The handoff completed.** The swap stopped the cortex and started the deep model, and the deep
  model reached `ready` 133 s after the start, 1.5 times the two uncontended loads drawn the same
  night (88 and 87 s). It decoded at 32.6 tokens/s, inside the 32.0 to 35.7 of the uncontended
  runs, so it ran on the card. `memory.used` peaked at 23425 of 24463 MiB, and with the deep model
  stopped it read 3632 MiB while the side container still ran: the driver had moved the idle
  process's buffers off the card to make room. The cortex was `ready` again 35 s after the deep
  model stopped.
- **The overlay** showed the same chips and reply as an uncontended handoff, and the store held the
  question, the cortex's hand-over sentence and the deep reply.
- **The side process came back.** Its first request took 1.95 s, against 0.09 s for the next, and
  moved 5618 MiB back onto the card. A cortex request at once after it took 0.09 s, as before.
- **After removing it** `memory.used` read 9328 MiB with the cortex loaded, below the 10834 MiB
  read when the stack came up.

So on this driver an idle process holding card memory slows the deep load and does not fail it.
The opt-in fit check reads the free memory before the load, so with `CORTEX_SWAP_BRAIN_VRAM_MIB`
set it would have refused this handoff, which then completed with the deep model on the card. No
defect was found here.

## Redis at its memory limit

`CONFIG SET maxmemory` on the stack's Redis, with its `noeviction` policy, then a turn. The limit
was set back to 0 after each flow.

- **Below what Redis held.** "What is 2 plus 2?" in a new chat ended at once with a red bubble,
  `session_store_unavailable: append to session '<id>' failed`, under the question. The question's
  own append failed (`OutOfMemoryError` on `RPUSH`), so nothing of the chat was stored and it was
  not in the chat list. The link dot stayed green.
- **3000 bytes above what Redis held**, then a pasted 10000-character question. Both the question
  and the reply were stored: the question's append went past the limit, and the reply's append was
  still accepted. A second write after that would have been refused.
- **Set during the deep model's load**, 2 s after the card was approved. The deep model loaded,
  answered, and its reply showed in full. The brain logged the record's `brain_active` state as
  not written, then failed to append the deep reply; the swap back still ran, and the cortex was
  `ready` 42 s after the deep model stopped. Only then did the red `session_store_unavailable`
  bubble show under the deep reply. The store held the question and the hand-over sentence, and
  no deep reply. The brain logged `a handoff ended failed` with "the session store failed while
  the handoff ran, so no deep reply was stored"; the record's `failed` state was refused too, and
  the record was deleted, so no handoff record was left behind. A second run gave the same.
- **The next turn after lifting the limit**, "What did the deep model say, in one line?", was
  answered with a one-line account of the proof, given as the deep model's words, though no deep
  reply was in the chat it read.

The bubble's text is the code and the brain's message, with the chat's id in it, and the same
under a full Redis as under a stopped one
([readings](store-and-process-restarts.md#redis-with-the-session-stores-retry)). It does not say
that the reply above it was not kept, which a full Redis makes true of every reply until the limit
is raised. That case is now part of
[R-814](../refinements/tasks/814-a-reply-that-ends-early-names-the-transport-not-the-cause.md).

## A new chat while the deep model loads

`Ctrl+N` 6 s into the deep load, then "What is 5 plus 5? One line." sent in the new chat. The
model host stopped the deep model and started the cortex, as for a Stop at that point. The old
chat stored the question and the hand-over sentence, and its record was left `failed` with "the
turn was torn down before the handoff finished". The new chat showed its question and the chip
"waiting for another request's handoff to the deep model to finish" until the cortex was back, and
its reply, "5 plus 5 is 10.", was stored 40 s after it was sent.

## A new chat while the cortex comes back

`Ctrl+N` 0.5 s after the deep model stopped, while the chip read "bringing the usual assistant
back", then the same question in the new chat. The old chat stored the question, the hand-over
sentence and the whole deep reply, since the deep phase stores its reply before the swap back. The
swap back finished, and the new chat's reply was stored 41 s after it was sent, under the same
waiting chip as above. The brain logged `a handoff ended failed` with "the turn was torn down
during the swap back, after the deep model's reply was stored", and the record kept that reason in
Redis for its hour. A second run gave the same, its reply stored 40 s after it was sent.

**The waiting chip names a handoff that is over.** After `Ctrl+N` the new chat's chip said it was
waiting for another request's handoff to finish, in both flows, while the person had just left that
request and the brain was reloading the cortex. Filed as
[R-877](../refinements/tasks/877-the-wait-behind-a-swap-back-names-a-handoff-that-is-over.md).
Since 2026-10-26 the queued turn's chip changes to "bringing the usual assistant back" when the
swap back begins, which `test_turn_handoff_wait.py` checks over a held restore; neither flow has
been run on the shell again since.

Method: the drivers (`flowc.sh`, `lib.sh`, `mon.sh`) and frames are in the run's scratch directory,
not in the tree.
