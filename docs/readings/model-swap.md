# Readings: what a model swap costs

How long the model host's control calls take and what a handoff's swap costs end to end. Cited by
[ADR-0030](../adr/ADR-0030-brain-handoff.md) (the risk on swap latency, the drain bound),
[ADR-0053](../adr/ADR-0053-model-host-supervisor.md) decisions 3 and 11 (the stop bounds and their
pairing) and [ADR-0055](../adr/ADR-0055-co-residency-and-spill-watch.md). The procedures that take
these readings are in the [model-swap](../runbooks/model-swap.md) runbook.

## A handoff at tier scale

**2026-08-07**, 24 GB card, the shipped cortex (gemma-4-12B QAT q4_0) and deep pick (gemma-4-31B QAT
q4_0), artifacts warm in the page cache, through the real `model-host` control API: stopping the
cortex took 0.7% of the deep model's time to reach `ready` (0.48 s against 70.03 s), stopping the
deep model 1.3% of it (0.89 s), and bringing the cortex back 45% of it (31.43 s). The swap both ways
was 1.47 times the deep load alone (102.9 s). A cold deep load, 99.6 s from start to `READY` in
[ADR-0004](../adr/ADR-0004-model-lineup.md)'s lineup, makes the swap about 1.9 times the warm load.
Method: timed `start`, `stop` and `status` polls against the control API.

## A handoff through the conductor

**2026-10-02**, 24 GB card, the shipped cortex and deep pick (deep context 16384, no drafter), each
row on its own `cortexswap` stack, every handoff approved by the headless handoff client. The rows
were drawn twice: a first draw read by hand after the client failed its own phase check, and a
replication of the swap and kill rows with the client fixed, which passed every check. A last swap
row ran a brain image whose deep model context ends with a message addressed to it; every earlier
row ran the image before that change, the old image below. Other agents' CPU work ran on host cores
0 to 11 throughout and shared them with the model host's 8-CPU quota, so every timing here is from
a loaded host. The SM clock read 0.51 to 0.67 of `clocks.max.sm` in the 5 s samples beside the
handoffs and 0.46 to 0.66 in the run's 15 s samples, with the power cap active in 9 of 139.

- **The phases**, seventeen approved handoffs over six rows. The drain took no time, since the
  stack ran no subagent pool. The cortex left `ready` within the sidecar's 1 s poll of the loading
  detail. The load, from the loading detail to the working detail, was 0.87 to 0.96 times the
  control API's warm 70.03 s in fourteen handoffs and 1.36 times it for the first draw's first deep
  load; that slowest load is 0.32 of `CORTEX_SWAP_LOAD_TIMEOUT_S`. The swap back, from the
  restoring detail to `TurnComplete`, was 0.92 to 1.09 times the control API's 31.43 s cortex
  return. On the old image the deep phase, from the working detail to the end of generation, was
  under 0.06 times the warm load, for replies of 35 to 97 tokens decoded at 32.0 to 35.7 tokens/s,
  and a whole handoff turn, from the client's send to `TurnComplete`, was 1.54 to 1.65 times its
  own load, and 1.38 times it for the first; no 5 s sampler caught that decode. `Health` read
  `ready=false` from the first poll after the loading detail until the turn ended. The brain sent
  the working detail twice in every handoff that reached it, once when the deep generation started
  and once when it ended.
- **The memory.** The card's `memory.used` peaked 19801 to 19823 MiB above the 619 to 638 MiB it
  read before each swap row, leaving at least 4021 of its 24463 MiB free. The model-host
  cgroup's `memory.peak` was 19.29 to 19.44 GB in every stack, 1.09 to 1.10 times the 17.65 GB
  artifact, whatever the memory cap.
- **The caps**, one approved handoff per stack. Against the stack at 24g and 8 CPUs, the load was
  1.03 times at 21g, 0.99 times at 19g and 0.99 times at 4 CPUs, and the decode rate 0.93, 0.93 and
  1.00 times, each rate over one reply of 36 to 97 tokens. No stack reached its memory cap: at 19g
  (20.40 GB) `memory.peak` was 19.32 GB.
- **The kill**, the same in both draws. A `kill -9` on the deep child about 1 s into its load ended
  the turn with `TurnComplete` and the "could not be loaded" note, and no working detail. A
  `kill -9` once the deep reply had started ended it with ten words of reply, the "stopped partway
  through" note and no restoring detail. The cortex was `ready` again 0.84 to 0.96 times its
  31.43 s return after the deep child stopped, and the ordinary turn sent next in each chat named
  the earlier question.
- **The reply.** On the old image, in all ten completed handoffs, the deep model wrote one sentence
  saying the task had been handed to the deep model, and never answered it. Its context ended with
  the escalation's result, which tells the cortex to tell the user what is being handed off, after
  the cortex's own reply saying so. With the context ending in `HANDOFF_TAKEN_MSG` and that reply
  left out, all three handoffs answered in two sentences, the first two under the old client
  prompt that told the model not to answer. The deep model then reasoned first: the deep phase was
  0.19 to 0.33 times the warm load, for 439 to 756 tokens at 34.1 to 35.7 tokens/s, and a whole
  handoff turn 1.74 to 1.90 times its own load.

Method: run 2 of `measurements/sitting-2026-10-02b/`, rows `772swap`, `772kill` and `772caps`
(drivers `swap.sh`, `kill.sh`, `caps.sh`), their replication `772swapb` and `772killb`, and
`777swap` (driver `777swap.sh`, the brain image built from the context change), with the client of [a handoff without the overlay](../runbooks/model-swap-measurements.md#a-handoff-without-the-overlay).
Phase times are the client's own clock, sidecar states its 1 s polls of `GET /models/{model}`, and
decode rates the brain's `the deep model's decode rate for this handoff` log line.

## What an eviction costs

**2026-07-18**, 8 GB card, small stand-ins (`Qwen3.5-0.8B-Q8_0` as the cortex tier,
`Qwen3.5-2B-Q4_K_M` as the deep one, `--ctx-size 4096`): stopping an idle child took 0.10 to 0.40 s,
while the two loads took 11.3 and 18.0 s, so the load is the whole cost. Stopping a child with a
request in flight took 10.09 s and 10.90 s: `llama-server` logged `cleaning up before exit` and did
not exit, because the shipped tiers run `--parallel 1`, so the whole 10 s SIGTERM grace was paid and
the child was killed. A busy eviction therefore costs about 25 times an idle one on that card.
Method: `POST /models/{model}/stop` timed with and without a stream in flight, VRAM read with
`nvidia-smi`.

## A stop queued behind a status

**2026-07-18**, 8 GB card, a SIGSTOPped child on the shipped grace: a stop took 10.89 s with the
per-model lock free and 15.70 s when issued 0.2 s behind a status, the status itself taking 5.80 s
(the probe timeout plus overhead). So the worst stop is the probe timeout plus the grace plus the
reap bound, which is why all three enter the pairing rule. Method: concurrent `status` and `stop`
against a stopped process.

## The fit check and the unhosted refusal, live

**2026-08-07**, 24 GB card: with the cortex resident the sidecar reported 61% of the card free
(14905 of 24463 MiB) against a declared deep cost of 78% of it (19125 MiB), and the swap in refused
in 0.03 s with nothing started; with the cortex evicted, the same call passed and the deep model
reached `ready` in 69.24 s, leaving 15% of the card free. Method: `test_model_host_live.py`,
integration-marked.

**2026-08-16**, 24 GB card, a sidecar whose roster held only the cortex: before the refusal a
handoff stopped the cortex, met a 404 on the deep tier and reloaded the cortex, 29.7 s with no
tier serving; with the refusal the conductor made one `GET /models/brain` and answered in under
0.01 s with the cortex serving throughout. Method: the real `SwapConductor` over the real
`HttpModelHost` and sidecar image.

## An undersized card does not fail

**2026-07-19**, 8 GB card, the cortex evicted and the deep tier pointed at a 17 GB artifact:
llama.cpp logged `failed to fit params to free device memory`, kept every layer on the GPU, and the
tier reached `READY` after 373 s, 1.24 times the 300 s load bound, then generated 16 tokens in 36 s.
The driver paged into host memory rather than refusing, so a tier-scale swap on a card too small
for it looks like a pass with meaningless numbers. Method: a manual start through the control API.
