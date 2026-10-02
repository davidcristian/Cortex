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

1. **The approving client**, an `#[ignore]`d live test in `body/crates/rpc/tests/` beside
   `live.rs`, with a `just` recipe beside `rpc-health`. It drives `BrainRpcClient::converse` with a
   channel-backed `decisions` stream, approves a `ConfirmRequest` only when `tool_name` is
   `escalate_to_brain`, denies every other one, keeps the stream open until it has answered, and
   prints one line per `TurnEvent` with the milliseconds since the turn was sent. The prompt comes
   from an environment variable whose default asks for the handoff by name. It fails when no
   `escalate_to_brain` request arrives, when the four `swapping` details do not arrive in order, or
   when the turn ends without `Complete`. Nothing in the brain changes: the confirm boundary stays
   on the client the user runs, which is where [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
   puts it. No CPU run proves it first, since the Echo fake calls no tool; the first card row does.
2. **The rows**, each written here with its command, price, rule and prediction before the draw,
   priced at twice the estimate because both tiers think before they answer. The stack image is
   five weeks old, so build it first, which is CPU work beside any card run.
   - **Swap and phases** (H-018, H-020): the deep tier named at 16384 with no drafter,
     `CORTEX_ESCALATION=1`, `CORTEX_MODELHOST_BACKEND=supervisor`, the loopback override for 1 s
     polls of `GET /models/*`, and a second client reading `Health` every 2 s. Three handoffs, the
     first cold. Read each phase off the status stream, split eviction from load with the sidecar
     polls, and take `nvidia-smi` used memory and SM clock every 5 s. About 12 minutes, priced 25.
   - **The kill** (H-019): `kill -9` on the deep child once at the `loading` status and once at
     the first text after `working`, each followed by one ordinary turn on the same session. About
     8 minutes, priced 15.
   - **The caps** (H-023): one handoff at the shipped 24g memory cap, two lower caps chosen from
     the first row's cgroup `memory.peak`, all above the deep artifact's size, and `cpus` 4
     against the shipped 8, reading load time, decode rate and `memory.peak`. About 20 minutes,
     priced 40.
3. **The close** writes the readings into [model swap](../../readings/model-swap.md) and the
   runbooks, edits ADR-0030 where a row changes what it states, and edits
   [ADR-0012](../../adr/ADR-0012-resource-governance.md) and the compose comment on the caps for
   the values the caps row sets.

## History

- 2026-10-02: filed by a probe of the four host items, which found that each needs the overlay
  only for what the user sees and that the GPU half is the agent's once a client answers the card.
  H-018, H-019 and H-023 now keep only that half, H-020 is declined into this task, and ADR-0030
  decisions 7 and 9 and the host index no longer give the confirm card as a reason for the desktop.
