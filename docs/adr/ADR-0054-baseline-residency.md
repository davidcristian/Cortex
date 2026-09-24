# ADR-0054: The baseline residency and what the brain reports about it

**Status:** Accepted (2026-08-19)

## Context

With escalation on, the GPU changes hands ([ADR-0030](ADR-0030-brain-handoff.md)). Between handoffs
it should hold the **baseline residency**: the cortex, plus every peer tier named in
`CORTEX_SWAP_EVICT_MODELS` (the GPU-placed subagent tier when one is hosted). Three things can make
the machine differ from that: a swap in progress, a restore or a startup that could not bring the
cortex up, and a peer that is not running. The user reads the brain's answer on the overlay's
connection dot through `Health`, whose `HealthReply` has `ready`, a `detail` line and `notes`; the
subagent placer needs to know when no GPU tier is serving, or it sends spawns at a dead server.

This record decides where that answer comes from, how startup recovery's result is scoped, and what
keeps a peer's state current. With escalation off the plain `SingleResidentModelManager` holds no
residency, the brain's residency is `None`, and `Health` stays unconditionally ready.

## Decision

1. **`Health` reads the manager's own published report.** `ResidencyReport(serving, detail)` is
   published by `SwappingModelManager`, the one object that changes residency, through the
   `ResidencyReporter` port (`residency()`, `ports_models.py`). The port is **synchronous by
   contract**, so a probe can never take the GPU lease and hang the indicator for a whole load. The
   handoff record was rejected as the source (it is live through the drain, while the cortex still
   serves, and it is Redis I/O per probe), and so was `ModelHost.status` (an HTTP call into the
   supervisor's per-model lock per probe, measured slower than the probe interval under contention).
   The resident model and the report are written together under one condition with nothing awaited
   between them (`ResidencyBoard`, `residency_board.py`), so a lease and the gRPC answer cannot
   disagree. Six values (`residency_state.py`):

   | Report | `serving` | When |
   | --- | --- | --- |
   | `RESIDENCY_SERVING` | yes | the cortex serves |
   | `RESIDENCY_LOADING` | no | the swap in, eviction included |
   | `RESIDENCY_DEEP` | no | the deep model holds the card |
   | `RESIDENCY_RESTORING` | no | the swap back |
   | `RESIDENCY_LOST` | no | the restore gave up |
   | `RESIDENCY_BOOT_FAILED` | no | startup recovery did not see the cortex `READY` |

   The drain window stays ready, since the cortex still serves then. A serving report with nothing
   to add leaves `Health`'s detail as `cortex-orchestrator <version>`. The brain container's compose
   healthcheck asserts that the RPC answered, not that it said ready, since an accurate
   `ready=false` would otherwise mark a working handoff unhealthy.
2. **Startup recovery's result is about the cortex and nothing else.** `converge_residency`
   (`swap_recovery.py`) clears the deep tier, clears the peers, settles the cortex, and answers
   whether the cortex was observed `READY`; `recover_handoffs` also fails any stranded record. The
   composition root publishes the answer with `publish_boot_residency(serving=...)` before the gRPC
   server starts. That publish is the one writer that touches the report without the resident model
   (`ResidencyBoard.publish_report`): an unanswered probe is not knowledge, and clearing the
   resident model would refuse every turn over a cortex that may come up a minute later.

   | What happened at startup | `ready` | Detail |
   | --- | --- | --- |
   | the host could not be reached | false | the usual assistant did not come up at startup |
   | the cortex would not become ready, or is not in the roster | false | the same line |
   | the deep tier is resident and its stop failed | false | the same line |
   | the roster has no deep tier | true | one `ERROR` naming `CORTEX_MODEL_FILE_BRAIN` and `CORTEX_ESCALATION` |
   | the cortex serves and a peer will not run | true | the model host is not running that peer |

   The deep tier is not a peer: a deep model that cannot be cleared is a reason to distrust the
   card, so its failure still decides the result, except `ModelNotHostedError`, which `_clear_deep`
   logs and swallows because there is no card to distrust when the name was never on it. The first
   two rows share a line because the operator's next move is the same; the log tells them apart,
   each line naming the call and the model it failed on ([ADR-0051](ADR-0051-log-line-rendering.md)
   decisions 7 and 8).
3. **A peer that is not serving is recorded, and GPU placement closes.** `BaselineTiers`
   (`residency_tiers.py`, held by the manager and handed out through `baseline_tiers`) maps each
   faulted peer to a `TierFault`: `MISSING` (not serving, worth asking again) or `UNHOSTED` (the
   roster has no such id; never asked again while that daemon runs). Any fault calls the placer's
   `close_gpu()`, so every spawn is placed on the CPU, and an emptied record calls `open_gpu()`. It
   is one bit for the card, not arithmetic (a charge large enough to crowd the cap would say "no
   room" where the truth is "no server"), and it cannot tell tiers apart, since no setting maps a
   hosted tier id to the GPU endpoint a roster entry dials. Over-refusing the GPU costs decode rate;
   under-refusing costs a dead load and a CPU re-run per spawn. The record holds a reason per tier
   and nothing else (no timestamp, no attempt count): the pass interval paces the retry. The writers
   are the swap back's and startup's shared `residency_moves.restart_evicted` and the pass (decision
   4).
4. **A periodic pass recomputes the record from the machine.** `TierRechecker`
   (`residency_recheck.py`) runs `SwappingModelManager.recheck_residency` every
   `CORTEX_SWAP_TIER_HEAL_S` (30 s). Its first half, `recheck_tiers` (`residency_pass.py`), asks
   `status` for **every** evict-list tier whatever the record says: `READY` marks it present,
   `LOADING` is left for a later pass, anything else is marked `MISSING` and started once, and a
   404 marks it `UNHOSTED`. A host that cannot answer marks nothing, so one transport blip cannot
   close the GPU for the pool. A pass never raises, and costs
   at most 2N + 2 control calls for N peers (two more only while the report is not serving, decision
   5). The pass does nothing while a handoff owns the card: its condition is the residency scope's
   flag **or** the handoff claim, read synchronously before every `start` with nothing awaited
   between. So only an observation taken outside a handoff marks anything, and a swap's deliberate
   eviction never reads as a fault. A start already in flight when a handoff begins is ordered by
   the supervisor's per-model lock against the swap in's stop when the daemon serves it first; when
   it does not, the peer loads beside the deep model and the handoff is refused by its fit check or
   spills. Neither loses state or corrupts the record; taking the GPU lease for the start would park
   a user's turn behind a load. `note_on` annotates only a **serving** report, so a swap window
   keeps its own words.
5. **A read-only regain ends a report that no turn can clear.** After a restore gives up, nothing is
   resident, `acquire` refuses every turn, and no turn means no handoff to reconcile anything. The
   pass's second half, `regain_residency` (`residency_regain.py`), returns at once while the report
   is serving; otherwise it publishes `RESIDENCY_SERVING`, with the placer's baseline charge
   restored, only when the cortex reads `READY` and the deep tier is off the card (`STOPPED`,
   `FAILED` or unhosted), because a cortex brought back by hand beside a deep model still resident
   is a spill or an out-of-memory load. An unanswered read publishes nothing. The publish is
   `publish_between_handoffs`, which tests the condition under the board's lock, so a handoff
   claimed mid-pass wins. It never starts, stops or converges anything: converging would bounce a
   co-resident plan's peers, and starting the cortex is a whole load on a shutdown path, a retry
   policy over an attempt that already failed twice. It never turns a serving report back.
6. **This state lives in the process and is recomputed from the machine.** The hard rule is about
   state that cannot be recomputed: conversation, tasks, working memory. What is resident and which
   peers are down is a reading of the machine, the same kind as the placer's VRAM ledger, and a pass
   or a startup re-reads it. A store would add a second writer with no locking and a record that
   outlives the daemon it described. Another process's handoff can at worst make one pass read a
   deliberately stopped tier as missing, which costs one interval of CPU placement.
7. **Notes reach a serving report in one place, and stay separate.** `residency_state.with_note`
   is the only way a note reaches a report: it appends to `ResidencyReport.notes`, the baseline
   condition first (`TIERS_MISSING_DETAIL`, "the model host is not running `<tiers>`, so delegated
   work is running on the CPU"), the last handoff's pace second
   ([ADR-0055](ADR-0055-co-residency-and-spill-watch.md) decision 5), and neither over a report that
   is not serving. Notes are composed at read time in `residency()` (`residency_probe.py`), so the
   regain's bare republish cannot erase one. `Health` sends each note as its own `HealthNote` and
   joins them with `; ` into `detail`, so a client built before `notes` existed still reads both.
   The overlay shows `Brain ready` with one line per note and keeps the dot green: turns run, and
   only where delegated work runs has changed. `HealthNote` has only its sentence; a code a client
   could style or dismiss one note by is added beside it when a client needs one, with its names
   picked then.

## Consequences

- A daemon replaced between handoffs is reconciled only at the next handoff or startup
  ([ADR-0053](ADR-0053-model-host-supervisor.md) decision 12); until then the pass's reads of the
  peers and the cortex are what keep the report current.
- A cortex that dies while both containers keep running is not restarted by anything automatic;
  restarting either container, or the runbook's manual step, brings it back.
- Residency changes are split by responsibility: `residency_moves.py` (what the host is asked to
  do), `residency_restore.py` (what the swap back promises), `residency_board.py` (the resident
  model, the report, the scope flag and their lock), `residency_claim.py` (`HandoffClaim`) and
  `residency_probe.py` (the report the user sees). `ResidencyBoard` and `HandoffClaim` are not
  exported from the core barrel.
- Every guard here is in-process ordering and promises nothing about a second brain process.

## Alternatives rejected

- **Widening `ResidencyReport` with per-tier state**: a report is republished at every transition,
  so a peer's fault written into it would be erased by the next swap in.
- **Checking the condition before calling publish**: a handoff claimed between the read and the
  write would have its own loading report overwritten by a reading taken before it started.
- **Checking peer readiness inside the swap back**: it spends the load limit per tier inside the
  turn the user is waiting on.
- **A second health sentence for the missing deep tier**: the one detail line belongs to the peers,
  and a configuration fact is not a readiness fact.

## Related

[brain-core](../modules/brain-core.md), [brain-orchestrator](../modules/brain-orchestrator.md),
[model-swap](../runbooks/model-swap.md), [ADR-0030](ADR-0030-brain-handoff.md),
[ADR-0053](ADR-0053-model-host-supervisor.md), [ADR-0055](ADR-0055-co-residency-and-spill-watch.md),
[ADR-0012](ADR-0012-resource-governance.md) (the placer).
