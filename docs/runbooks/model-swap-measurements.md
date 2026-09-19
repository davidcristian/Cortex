# Runbook: what a model swap costs

What the swap mechanism costs at small scale, whether two tiers fit on one card, what the fit
check before a load is worth, and how the brain reports a tier that spilled to host memory.
Turning escalation on and every setting named here: [model-swap.md](model-swap.md). Recovering a
handoff that left the GPU wrong: [model-swap-recovery.md](model-swap-recovery.md). Decision:
[ADR-0055](../adr/ADR-0055-co-residency-and-spill-watch.md).

## The mechanism, as measured

Validated 2026-07-18 on an 8 GB card (8188 MiB, driver 610.74, 2516 MiB used at rest), with two
small artifacts in place of the tiers: the cortex tier pointed at `Qwen3.5-0.8B-Q8_0.gguf` and
the deep tier at `Qwen3.5-2B-Q4_K_M.gguf`, both at `--ctx-size 4096`. Every number is one
observation on that card, not a benchmark, and **every number is the mechanism's rather than a
tier's**: gemma-4-12B alone takes 7715 of that card's 8188 MiB.

| Step | Command | Observed |
|---|---|---|
| boot | `up -d model-host` | control API answering at once; cortex child spawned, `{"state":"loading","detail":"pid 9 is not serving yet"}`; compose healthcheck went `healthy` when it turned ready |
| resident | `GET /models/cortex` | `{"state":"ready","detail":"serving on port 8080"}`; `/v1/models` on 8080 named the 0.8B path; VRAM 3501 MiB (about 985 MiB for the model) |
| evict, idle child | `POST /models/cortex/stop` | answered in **0.40 s**; no `llama-server` in `ps`; 8080 refused connections; VRAM back to **2513 MiB** |
| evict, child mid answer | `POST /models/cortex/stop` with a stream in flight | answered in **10.09 s** (**10.90 s** in a second run): llama-server logged `cleaning up before exit` and then did not exit, so the full `CORTEX_MODELHOST_STOP_GRACE_S` was paid, it was SIGKILLed, and the reap plus the HTTP round trip account for the rest. The shipped tiers run `--parallel 1`, so one in-flight request blocks the graceful exit. This is the eviction cost to plan for |
| load | `POST /models/brain/start` | answered in **0.007 s**, which is a spawn and not a load; `loading` immediately after |
| readiness | poll `GET /models/brain` | `ready` **18.0 s** after the start; `/v1/models` on 8081 named the 2B path; exactly one `llama-server` in `ps`; cortex still `stopped`; VRAM 3952 MiB |
| swap back | `POST /models/brain/stop` then `POST /models/cortex/start` | stop answered in **0.10 s** with the child idle; cortex `ready` **11.3 s** later, serving the 0.8B path again; deep tier `stopped` |
| the scope | `SwappingModelManager.swap_scope(deep)` over the real adapter (`just brain-modelhost-live`) | inside the scope the deep tier was READY and the other one STOPPED, and the endpoint the lease handed out was the deep tier's; after it, the reverse |
| end to end | one `Converse` turn through the brain container | `Health` ready, `text_delta`s, `turn_complete`; the reply came off the supervised child over `http://model-host:8080` |

**Do not run the tier-scale swap on an undersized card to see whether it works: it will say yes.**
Measured 2026-07-19 on the same card, with the cortex evicted first and the deep tier pointed at a
17 GB `gemma-4-31B-it-qat-q4_0` artifact, llama.cpp logged `failed to fit params to free device
memory: n_gpu_layers already set by user to 99, abort`, kept every layer assigned to the GPU,
reached `ready` after **373 s** with `nvidia-smi` at about 7.7 of the card's 8188 MiB, and then
served 16 tokens in 36 s, which is what the WSL2 driver spilling into host RAM costs. Nothing
failed, so nothing warns you, and every timing and VRAM number from such a run is meaningless.

Tier scale is minutes rather than seconds on both halves: an 18 GB GGUF off the model mount at the
measured mount read rate is what `CORTEX_SWAP_LOAD_TIMEOUT_S` exists for. The eviction half is
sub-second only while the child is idle; every path that evicts a tier which was answering pays
the whole grace per busy tier, which is what `stop_grace_period: 45s` on the container is sized
for (3 tiers times 10 s, plus slack, the shutdown pass being sequential).

## Co-residency, and how to tell a fit from a spill

Measured 2026-08-07 on a 24 GB card (24463 MiB, driver 610.88, llama.cpp build
`b10236-1464c62d8`) through this control API with the real tiers. Read the idle floor first and
subtract it: this machine's idle reading moved between 1529 and 2836 MiB inside one session,
because Windows' own desktop shares the card.

| Configuration | `nvidia-smi` used | Free | Deep decode | Result |
|---|---|---|---|---|
| cortex alone, 16K, projector, 1024-token image budget | 11284 to 11298 MiB | | | 8448 to 8468 MiB above floor |
| deep alone (gemma-4-31B q4_0, 8K, `-ngl 99`) | 20671 to 20723 MiB | ~3.8 GB | 25.07 to 33.28 tok/s | 19117 to 19125 MiB above floor |
| **cortex + deep** | 23539 to 23642 MiB | ~0.5 GB | **14.80 to 17.29 tok/s** | **spilled**, 4676 MiB short |
| **deep + gemma-4-E4B subagent tier** | 23555 to 23642 MiB | ~0.9 GB | **28.92 to 29.82 tok/s** | **fits**, peer costs 2878 MiB |

**The two bottom rows read the same on `nvidia-smi` and are opposite results.** A card 4676 MiB
short does not refuse the second load: both tiers report `ready`, the stream works, and the WSL2
driver pages about 6 GB to system memory. The tell is decode rate, roughly halved, plus a prefill
that collapses to 13.8 tok/s on the first request after each switch where a fitting pair holds 105
to 134. So measure `predicted_per_second` from llama.cpp's own `timings`, on each tier, before and
after, and treat a memory reading alone as no evidence either way. The brain reads decode itself;
prefill it does not, so that half stays a hand measurement.

What co-residency buys, on the same run with the artifact warm in the page cache: `stop(cortex)`
0.48 s, deep tier `ready` 70.03 s later, `stop(brain)` 0.89 s, cortex `ready` 31.43 s later, so
102.9 s of swap either side of the deep phase, about 132 s cold. Without the flag every spawn is
refused for all of it and for the deep phase too; with it, delegated work never stops. Generating
on both tiers at once costs both (deep 18.74 tok/s, peer 22.91) and allocates nothing (23639 MiB
under load against 23642 idle), which is why a spawn onto an already-resident tier is not a VRAM
decision.

To reproduce, layer `docker/docker-compose.modelhost-loopback.yml`, name all three artifacts, and
drive `POST /models/{id}/start` by hand with the cortex stopped first. The live suite has it as
`test_a_coresident_scope_leaves_its_peer_serving_beside_the_deep_model`
(`just brain-modelhost-live`), which skips unless the sidecar hosts all three tiers. The numbers
are in [two tiers on one card](../readings/co-residency.md).

### The fit check, and what it is worth

The sidecar answers `curl -s http://127.0.0.1:9300/health` with `device_free_mib` and
`device_total_mib` beside the roster and the three timing bounds, read with `nvidia-smi` inside
the container that holds the GPU reservation, and a swap compares `CORTEX_SWAP_BRAIN_VRAM_MIB`
against the free figure between its last eviction and its load. Measured on this card with the
cortex resident and the desktop quiet:

| What was resident | `/health` free | Declared need | Outcome |
|---|---|---|---|
| cortex (text only) | 14905 MiB of 24463 | 19125 MiB | **refused in 0.03 s**, nothing started |
| nothing (cortex evicted, as a handoff evicts it) | about 22.8 GB | 19125 MiB | loaded, `ready` in 69.24 s, 3579 MiB left free |

The sidecar's figure matched the host's own `nvidia-smi` exactly, which is the check worth running
first if a refusal ever looks wrong.

**A handoff also changes what the subagent placer will admit.** The residency scope charges
`CORTEX_SWAP_BRAIN_VRAM_MIB` against `CORTEX_VRAM_SOFT_CAP_GB` for the length of a handoff, in
place of `CORTEX_VRAM_CORTEX_GB`, so a GPU-placed spawn during a co-resident handoff is fit-tested
against the card as it is. At the shipped 14 GB cap that window leaves nothing at all, so the
measured 3.5 GiB subagent request is GPU-placed outside a handoff, overflows to the CPU server
while the deep model is resident, and is GPU-placed again once the cortex is back. Delegated work
through a co-resident handoff may therefore be slower than the same work outside one, and a
restore that gave up keeps every spawn on the CPU until somebody can describe the card again,
which the background pass does within one `CORTEX_SWAP_TIER_HEAL_S` of the cortex serving. With
`CORTEX_SWAP_BRAIN_VRAM_MIB` unset there is no charge and the placer behaves as it always did.

**Read a refusal as "there was not room", never a pass as "it fitted".** The check does not cover
a figure declared too low, and does not cover memory taken while a load runs, and both of those
end in the silent spill above. When a co-resident deep phase feels slow, do not read memory: read
`timings.predicted_per_second` off a completion on each tier and compare it against the solo rates
in the table.

### The spill watch, which runs that reading for you

`LlamaCppBackend` surfaces the server's `timings.predicted_per_second` as a `DecodeCadence` on
every completion, and a deep phase compares the best completion of the whole handoff against
`CORTEX_SWAP_BRAIN_DECODE_TPS`, the tokens per second you measured for that tier on this card. Set
it from a cold load of the tier alone, and set it as a floor rather than a target.

Under the floor it logs once per handoff at WARNING, and `shortfall` is the floor minus the best
rate the tier managed. At or above it, the same fields at INFO without `shortfall`. With
`CORTEX_SWAP_BRAIN_DECODE_TPS` unset, the INFO line and no result, which is what an unmeasured
deployment gets rather than a boot failure. No reading at all also logs at INFO and is not a pass:
a completion under 32 decoded tokens is not judged, and a phase that failed before decoding
anything reports nothing. `samples` is how many completions reported a rate and `judged` how many
were long enough to count. The three lines, with every value a placeholder:

```
WARNING:cortex_core.brain_phase:the deep model decoded below the rate this deployment measured for it, which is what an overcommitted card looks like: the load was not refused, it was paged to host memory decode_rate=<the best rate> decoded=<tokens in the best completion> floor_rate=<the floor you set> judged=<completions long enough to count> model=<the deep model> samples=<completions that reported a rate> session_id=<chat id> shortfall=<floor minus rate> turn_id=<turn id>
INFO:cortex_core.brain_phase:the deep model's decode rate for this handoff decode_rate=<the best rate> decoded=<tokens in the best completion> floor_rate=<the floor, 0 when none is set> judged=<completions long enough to count> model=<the deep model> samples=<completions that reported a rate> session_id=<chat id> turn_id=<turn id>
INFO:cortex_core.brain_phase:no decode rate was reported for this handoff, so nothing was checked; a completion too short to judge, a failed phase, or a backend whose engine reports no timings all read alike model=<the deep model> session_id=<chat id> turn_id=<turn id>
```

All three name the turn that escalated, so `grep turn_id=` on that id returns the decode reading
beside everything else that turn wrote.

**The result also reaches the overlay**, because the log is no use to an operator who is not
tailing a container. A handoff that ran under the floor makes `Health` answer `ready=true` with
`the last deep task ran far slower than this deployment measured for it, so deep tasks are taking
much longer than they should`, which the connection tooltip shows as `Brain ready: <that line>`.
The dot stays green, and that is correct: turns work and delegation works, and what is wrong is
that deep tasks cost roughly twice what they should. The note is about the last handoff, not about
now: it clears the moment a later handoff reaches the floor, and lapses on its own after an hour
if no handoff decides it either way. Restarting the brain also clears it, which is also what
applies a corrected `CORTEX_SWAP_BRAIN_DECODE_TPS` or `CORTEX_SWAP_BRAIN_VRAM_MIB`. A missing peer
tier and a spill are said together, joined by a semicolon, since they have different fixes: put
the tier back, and give the card room.

The watch covers only the deep phase, since only a handoff changes what is on the card, and it
never touches the turn: the reply has already streamed by the time the rate is known.

Measured on this card 2026-08-08 through the shipped adapter and watch, three completions of about
120 words per condition. The last two rows are reproducible with
`packages/inference/tests/test_decode_cadence_live.py`; start or stop the peer through the control
API to choose which. The cold row came from a script driving the same adapter, so reproducing it
means arranging a clear card yourself.

| Condition | free after | decode | best | at a declared 25.0 |
|---|---|---|---|---|
| deep alone, cold onto a clear card | 2310 MiB | 31.08, 31.85, 33.78 | 33.78 | not collapsed |
| **cortex resident, then deep** | **423 MiB** | **21.64, 20.38, 22.77** | **22.77** | **collapsed**, 2.23 short |
| deep alone, peer evicted under it | 8649 MiB | 28.32, 29.82, 29.38 | 29.82 | not collapsed |

Two things to remember from it. A spilled tier does not fully recover when its peer is evicted
(29.82 against 33.78 from cold, at 8649 MiB free where the cold load read 2310), and which tier
pays depends on load order: loading the cortex second, beside an already-resident deep model, cost
the deep model less (23.28 tok/s at best), the driver paging the newcomer first. A handoff always
loads the deep model second, so the middle row is the one that matters, but a report of a slow
cortex after a handoff is the same fault read from the other end.
