# A headless client that approves the handoff card

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-10-02

The tier-scale handoff ([H-018](../../host/tasks/018-tier-scale-swap.md)), the kill during one
([H-019](../../host/tasks/019-chaos-kill-tier-scale.md)), its phase timings
([H-020](../../host/tasks/020-measured-swap-timings.md)) and the cap numbers measured against it
([H-023](../../host/tasks/023-cgroup-cap-numbers.md)) were host work for one reason: a handoff
starts only after the user approves the `escalate_to_brain` confirm card, and the overlay was the
only client that answered a `ConfirmRequest`. That reason does not hold, and nothing else in those
four needs the Windows desktop. Checked against the tree on 2026-10-02:

- The approval is a client message and nothing more. `RpcConfirmer`
  (`brain/packages/orchestrator/src/cortex_orchestrator/confirm.py`) resolves a pending request on
  any `ConfirmResponse` with its `confirm_id` on the same `Converse` stream, from whatever client
  holds the stream and the RPC token.
- The body's own client already sends one. `BrainTransport::converse`
  (`body/crates/core/src/transport.rs`) takes a `decisions` stream of `ConfirmDecision`, and
  `body/crates/rpc/src/converse.rs` chains it onto the `UserTurn`.
- `just rpc-health` answers none because its live test sends the `UserTurn` from
  `tokio_stream::iter` and so half-closes at once, and the brain then denies every pending confirm
  (`_pump` in `converse_stream.py` calls the confirmer's `close`).
- With `CORTEX_ESCALATION` set every turn gets an escalation slot (`escalating_engine.py`), and a
  turn that has read no untrusted content is untainted, so its `escalate_to_brain` call is put to
  the client rather than denied.
- The phases are on the stream: the swap yields `StatusUpdate(state="swapping")` with the four
  details in `cortex_core/swap_notes.py` (draining, loading, working, restoring), then
  `TurnComplete`.

**The card holds it.** The deep pick costs 19117 to 19125 MiB above the idle floor at an 8192
context and about 665 MiB more at the shipped 16384; the cortex costs 8448 to 8468 MiB
([model-swap-measurements](../../runbooks/model-swap-measurements.md)). A handoff stops the cortex
before the load, so the peak is the deep tier alone, about 19.8 GB above a floor that read 3.4 GB at
the start of the 2026-10-02 card run: 23.2 of the card's 24.46 GB. Leave the drafter unnamed; its
997 to 1020 MiB would leave about 260 MiB. Both artifacts are on the mount:
`/mnt/ai/Models/google/gemma-4-31B-it-qat-q4_0-gguf/gemma-4-31B_q4_0-it.gguf` (17651001568 bytes)
and the cortex's `gemma-4-12b-it-qat-q4_0.gguf` (6975879296 bytes). The control-API half is already
measured ([model swap](../../readings/model-swap.md#a-handoff-at-tier-scale)); what no run has done
is a handoff through the brain's conductor, from an approved card to the cortex serving again.

**What to build.**

1. **The approving client** is built: `just rpc-handoff approve` (or `deny`), an `#[ignore]`d live
   test in `body/crates/rpc/tests/handoff_live.rs`, with its settings and output in
   [model-swap-measurements](../../runbooks/model-swap-measurements.md#a-handoff-without-the-overlay).
   It drives `BrainRpcClient::converse` with a channel-backed `decisions` stream, approves an
   `escalate_to_brain` card only when its command line says `approve`, denies every other card,
   keeps the stream open until the turn ends, and reads `Health` on a second connection every 2 s.
   Nothing in the brain changed: the confirm boundary stays on the client the operator runs, which
   is where [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md) puts it. Against the Echo brain
   on CPU a `deny` turn completed and an `approve` turn failed on the missing card, as it should;
   the Echo fake calls no tool, so the first card row is the first run of the approve path.
2. **The rows** are queued, not drawn: `measurements/sitting-2026-10-02b/drivers/` holds the
   launcher, the queue and one driver per row, and each row below was written here before any
   draw. The prices are twice the estimate, because both tiers think before they answer. The
   `cortex-brain` and `cortex-model-host` images were rebuilt on 2026-10-02 from the tree that
   filed this task, the second on the local `server-cuda` engine image the night's other card rows
   use. Every row runs the stack as compose project `cortexswap`, with its own Redis volume: the
   deep tier named at 16384 with no drafter, `CORTEX_ESCALATION=1`,
   `CORTEX_MODELHOST_BACKEND=supervisor`, the loopback override, and a fresh `CORTEX_SEAM_TOKEN`.
   Beside each handoff it reads the sidecar's `GET /models/cortex` and `/models/brain` every 1 s,
   `nvidia-smi` used memory and SM clock every 5 s, the container cgroup's `memory.current` and
   `memory.peak` every 5 s, and `Health` every 2 s through the client.
   - **`772swap`** (H-018, H-020), `swap.sh`, priced 1500 s: three approved handoffs on one stack
     at the shipped caps (24g, 8 CPUs), the first being the stack's first deep load. *Decides*
     whether a handoff through the conductor completes at tier scale and returns the cortex, and
     what each phase costs. *Rule:* the agent half of H-018 passes when every handoff that got an
     approved card ends `Complete` with the four details in order and the sidecar shows the cortex
     `ready` within 300 s after. A load, from the loading detail to the working detail, above 240 s
     leaves the shipped `CORTEX_SWAP_LOAD_TIMEOUT_S` of 300 s under a fifth of margin, and the next
     slot raises that default. Peak used memory within 256 MiB of the card's 24463 MiB goes into
     ADR-0030 as a spill risk. *Prediction:* the cortex calls the tool in at least two of three
     turns, and every approved handoff completes. The deep load takes 0.9 to 1.6 times the 70.03 s
     warm load the control API measured, the first at most 1.9 times. The cortex leaves `ready`
     within 2 s of the loading detail, and the swap back, restoring detail to `Complete`, takes 0.8
     to 1.5 times the cortex's 31.43 s return. Peak used memory is 22.6 to 23.6 GB. A null result
     is no card in three turns: the default prompt does not reach the tool, and the row is drawn
     again with a prompt that writes the brief out.
   - **`772kill`** (H-019), `kill.sh`, priced 900 s: one stack, a handoff with `kill -9` on the deep
     child as soon as it exists after the loading detail, then an ordinary turn in the same chat
     asking what was handed off, then a handoff killed at the first `Delta` after the working
     detail, then the same ordinary turn. *Decides* whether the hard rule holds under a kill.
     *Rule:* a lost chat (an ordinary turn whose reply does not name the odd-numbers question, or a
     failed session read) or a cortex not `ready` within 300 s is the most serious finding either
     backlog can produce, and gets a replication written here before any design change.
     *Prediction:* the load kill ends `Complete` with the "could not be loaded" note and no working
     detail. The answer kill ends `Complete` with partial text and then the "stopped partway
     through" note, with no restoring detail, since the swap back runs as the swap scope exits. The
     cortex is `ready` again within 1.5 times its 31.43 s return each time, and both ordinary turns
     name the earlier question.
   - **`772caps`** (H-023), `caps.sh`, priced 2400 s: four stacks with one approved handoff each:
     24g with 8 CPUs, two lower memory caps with 8 CPUs, and 24g with 4 CPUs. The lower caps follow
     a rule fixed before the draw: the high cap is the swap row's `memory.peak` in whole GiB, held
     between 21 and 22, and the low cap is the deep artifact plus 2 GiB rounded up, 19g. Each
     handoff reads its load time, the deep tier's decode rate from the brain's cadence log line, and
     `memory.peak`. *Decides* the cap values ADR-0012 and the compose comment state. *Rule:* a cap
     pair is safe when its handoff completes with a load within 1.25 times and a decode rate within
     0.9 of the same row's 24g and 8 CPU handoff. The close writes the lowest safe memory cap into
     ADR-0012 as the floor, keeps 24g as the default unless a lower cap is safe at no cost, and
     writes 4 CPUs into the compose comment as a measured floor if it is safe. *Prediction:*
     `memory.peak` reaches the cap in every stack, since the page cache fills it; all three memory
     caps are safe, because the mapped artifact pages are file-backed and can be dropped; 4 CPUs
     loads within 1.1 times and decodes within 0.95, since every deep layer runs on the GPU.
3. **The close** writes the readings into [model swap](../../readings/model-swap.md) and the
   runbooks, edits ADR-0030 where a row changes what it states, and edits
   [ADR-0012](../../adr/ADR-0012-resource-governance.md) and the compose comment on the caps for
   the values the caps row sets.

## History

- 2026-10-02: filed by a probe of the four host items, which found that each needs the overlay
  only for what the user sees and that the GPU half is the agent's once a client answers the card.
  H-018, H-019 and H-023 now keep only that half, H-020 is declined into this task, and ADR-0030
  decisions 7 and 9 and the host index no longer give the confirm card as a reason for the desktop.
- 2026-10-02: the client is built and checked on CPU against the Echo brain. The four swapping
  details, the state and the tool name are tied to the brain's constants by `crosscheck.py`, which
  now reads a Rust or TypeScript string holding a `;`.
- 2026-10-02: the three card rows are written above with their drivers, rules and predictions, and
  queued behind the night's first card run in `measurements/sitting-2026-10-02b/`, none drawn yet.
