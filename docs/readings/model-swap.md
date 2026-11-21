# Readings: what a model swap costs

How long the model host's control calls take and what a handoff's swap costs end to end. Cited by
[ADR-0030](../adr/ADR-0030-brain-handoff.md) (the risk on swap latency, the drain bound),
[ADR-0053](../adr/ADR-0053-model-host-supervisor.md) decisions 3 and 11 (the stop bounds and their
pairing) and [ADR-0055](../adr/ADR-0055-co-residency-and-spill-watch.md). The procedures that take
these readings are in the [model-swap](../runbooks/model-swap.md) runbook.

## A handoff at tier scale

**2026-08-07**, 24 GB card, the shipped cortex (gemma-4-12B QAT q4_0) and deep model (gemma-4-31B QAT
q4_0), artifacts warm in the page cache, through the real `model-host` control API: stopping the
cortex took 0.7% of the deep model's time to reach `ready` (0.48 s against 70.03 s), stopping the
deep model 1.3% of it (0.89 s), and bringing the cortex back 45% of it (31.43 s). The swap both ways
was 1.47 times the deep load alone (102.9 s). A cold deep load, 99.6 s from start to `READY` in
[ADR-0004](../adr/ADR-0004-model-lineup.md)'s lineup, makes the swap about 1.9 times the warm load.
Method: timed `start`, `stop` and `status` polls against the control API.

## A handoff through the conductor

**2026-10-02**, 24 GB card, the shipped cortex and gemma-4-31B (deep context 16384, no drafter), each
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

## A handoff on the deep pick

**2026-11-21**, 24 GB card (24,463 MiB) beside the desktop's apps, engine build b12375 from the
`cortex-model-host` image, with a brain built from the tree, Redis and the model host from the
repo's compose files. Beside the models mount, four variables were named: `CORTEX_ESCALATION=1`,
`CORTEX_MODELHOST_BACKEND=supervisor`,
`CORTEX_MODEL_FILE_BRAIN=unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf` and
`CORTEX_SWAP_BRAIN_VRAM_MIB=16991`. Every other setting was on its compose default. Two runs, each
on a fresh stack: one without a drafter, one with `CORTEX_MODEL_FILE_BRAIN_DRAFT` naming the same
file. Each run is one chat of three turns: a code word to keep, a task the cortex handed over with
`escalate_to_brain`, and a question about both. The pass rule and the card's expected readings were
written before the first launch.

16991 is the highest reading of this file with its draft layer as the model host starts it
([R-1243](../refinements/tasks/1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md),
2026-11-18). That is the larger of the two launches, so the fit check compared the free figure
with a number at or above the cost of both. It passed with 19,441 and 19,456 MiB free. The model
host reports the card's `memory.free`, which was 315 and 318 MiB under the total less the floor.

Both deep servers started as `llama-server --model
/models/unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf --host 0.0.0.0 --port 8081 -ngl 99
--ctx-size 16384 --parallel 1 --jinja --cache-ram 0`, followed by the flags in the first row.

| reading | no drafter | draft layer |
| --- | --- | --- |
| rest of the argv | `--cache-type-k q8_0 --cache-type-v q8_0` | `--spec-type draft-mtp --spec-draft-n-max 3 --cache-type-k q8_0 --cache-type-v q8_0 --cache-type-k-draft q8_0 --cache-type-v-draft q8_0`, with no `--model-draft` |
| card's floor before and after | 4,707 and 4,680 MiB | 4,689 and 4,680 MiB |
| highest reading above the floor before | 15,950 MiB (expected 15,500 to 16,100) | 16,991 MiB (expected 16,800 to 17,200) |
| free at the highest reading | 3,806 MiB | 2,783 MiB |
| load, as a share of `CORTEX_SWAP_LOAD_TIMEOUT_S` | 0.28 | 0.19 |
| first token, as a share of `CORTEX_INFERENCE_STALL_TIMEOUT_S` | 0.027 | 0.028 |
| the deep request | 899 prompt tokens, 878 decoded | 899 prompt tokens, 103 decoded, 58 of 132 drafted tokens accepted |
| deep phase, swap back and whole turn, each over the run's own load | 0.31, 0.42 and 1.75 | 0.09, 0.62 and 1.74 |

- **While the deep tier served**, in both runs, the cortex was `stopped` and the deep tier `ready`.
  Redis held the session's list of 4 messages, `cortex:handoff:active` and the handoff's own key.
  No 1 s poll of the two tiers read both loaded.
- **After it**, in both runs, the deep reply was in the chat below the cortex's sentence about the
  handoff, with no note. The deep tier was `stopped` and a new cortex process `ready`. That
  process answered the third turn with the code word and the deep model's explanation. The
  session's list had all 7 messages, both handoff keys were gone, and the brain's log had no
  warning or error.
- **The load** is the deep server's own clock from its start to `listening`. The run without a
  drafter was the file's first load of the night. The client's clock, from the loading detail to
  the working detail, reads 0.278 and 0.186.
- **The first token** is the engine's prompt pass of the one deep request. The client's first
  reasoning delta came 0.028 and 0.029 of the stall bound after the working detail.
- **The effort.** Neither run named an effort, so both requests reasoned at the template's `xhigh`,
  and both ended on their own. The trace was 2,116 characters without the drafter, where the model
  wrote its reply twice and counted the words of each, and 120 with it. That is one draw each; the
  stop counts at 16384 are in
  [deep candidates](deep-candidates.md#the-stop-rows-at-16384).
  The drafted request decoded at 1.58 times the rate of the other, over replies of 103 and 878
  tokens.
- **The template.** Neither deep request had more than one leading system message, since the
  stack had no memory store and the chat no recap, so the brain's system message probe did not
  run ([R-1269](../refinements/tasks/1269-no-handoff-on-qwen38-27b-has-sent-three-leading-system-messages.md)).
  One more launch of the model host alone rendered three bodies through `POST /apply-template` on
  the deep server. Three leading system messages render in order as one system block below the
  `xhigh` sentence. Each earlier reply, and the `escalate_to_brain` call, renders behind an empty
  thought, and the request ends in an open thought. `/props` reports
  `supports_reasoning_effort` with the levels `low`, `medium` and `xhigh`, and
  `supports_preserve_reasoning`.

Method: `bash ~/.cache/cortex-run/2026-11-21/h1/run.sh nodraft none` and `run.sh draft layer`,
compose project `cortexn26`, which each script removes. A run's record is `logs/<label>/live.txt`
there, beside `turns.jsonl`, `states.txt`, `smi.txt`, `host.log` and `brain.log`, and
`python3 summary.py logs/<label>` prints its figures. `template.sh` is the render, with its bodies
and replies in `logs/template/`.

**The effort setting, 2026-11-21.** Two more runs of the same chat on the same build and stack,
both with the draft layer, from the tree that reads `CORTEX_REASONING_EFFORT_BRAIN`: one with the
setting at `medium`, one naming no effort. What the check decides was written before the first launch.

| reading | `medium` | no effort |
| --- | --- | --- |
| the brain's log | one `GET /props` of the deep server, then `reasoning effort sent` with `sent_as=medium` | no line about an effort and no `/props` request |
| the deep request | 861 prompt tokens, 97 decoded, 61 of 105 drafted tokens accepted | 899 prompt tokens, 503 decoded, 357 of 435 accepted |
| the deep trace | 67 characters | 1,199 characters |
| card's floor before and after | 4,564 and 4,556 MiB | 4,566 and 4,556 MiB |
| highest reading above the floor | 16,989 MiB | 16,989 MiB |
| load and first token, each as a share of its bound | 0.19 and 0.028 | 0.19 and 0.028 |

The 38 prompt tokens between the two requests are the `xhigh` sentence the template leaves out at
`medium`, the difference between the stop rows' 322 and 284. A deep request leaves out the cortex's
own sentence about the handoff, so both runs sent the deep server the same messages. Both runs read
as the drafted run above did: the same states and argv while the deep tier served, then the deep
reply with no note, the code word and the explanation in the third turn, all 7 messages, no handoff
key, and no warning or error in the brain's log. One draw at each setting says nothing about how
long a level reasons; the stop rows do. `/props` of the cortex server, gemma-4-12B on the same
build, reports `supports_reasoning_effort` false and an empty `reasoning_effort_levels`, the answer
on which the adapter sends no field. Method: `run.sh medium layer medium` and `run.sh unset layer
none` in `~/.cache/cortex-run/2026-11-21/b1/`, with `notes.md` and `logs/<label>/` as above.

## The overlay's view of a handoff

**2026-10-06**, 24 GB card, the shipped cortex and gemma-4-31B (deep context 16384), one `cortexov`
stack built from the tree, and the Linux shell: a debug build rendering through WebKitGTK in
software on an `Xvfb` display, its brain address and token the stack's. Every turn was typed and
every card approved by `xdotool` clicks. Four handoffs: one completed, one completed while a kill
waited for its answer, one killed about 6 s into its load and one killed at its first answer text.
The card's `memory.used` peaked at 22304 of 24463 MiB during the deep phase, from 3202 MiB before
the stack started. The SM clock read 0.51 to 0.68 of `clocks.max.sm`. No timing is published here.

- **The card** showed `escalate_to_brain`, the cortex's `brief` argument as a row, and the tool's
  reason as written. It stayed open until the click; the click closed it and the swap started.
- **The status lines.** "waiting for a tool to finish", then "loading the deep model; this takes a
  few minutes" for the whole load. The draining line arrives in the same millisecond as the loading
  line when no delegated work runs (the client's log of 2026-10-02 shows both at one `+ms`), so no
  frame showed it. "the deep model is working on this" showed for one 1 s frame, then the chip
  showed the deep model's reasoning a delta at a time (ADR-0020 decision 9), then "bringing the
  usual assistant back" until the turn ended. The chips dropped when the turn settled.
- **The dot** stayed green in all 868 frames of the run, sampled once a second, and its tooltip
  kept the pre-turn "Brain ready" line while `Health` read `ready=false`. Each streamed event marks
  the link ready, and a dismiss during a turn minimizes to the orb rather than hiding, so the
  summon probe does not run again until the turn ends. Each turn ended after the cortex was
  `ready`, so the probe after it read green.
- **The reply.** The deep model's text was appended to the cortex's hand-over sentence with no
  break ("equals $n^2$.Visually", "zero.The number") in all four. While the stream paused for the
  swap, the eight letters before the whisper's front stayed part condensed and the cortex's last
  word, which no whitespace had followed, stayed hidden ("odd numbers eq" and a blur), from the
  loading line until the deep model's first text.
- **The kills.** At load, the turn ended with the "could not be loaded" note, which called the
  cortex's hand-over sentence "the answer above". At the answer, the partial essay stayed in the
  bubble above the "stopped partway through" note. Both settled with the send button back and the
  dot green, and the ordinary turn typed next in each chat named the earlier request.

Method: `measurements/overlay-handoff-2026-10-06/`, with the shell started by `shell.sh`, frames
from `ffmpeg -f x11grab` at 1 frame/s, sidecar states 1 s polls of `GET /models/{model}`, and the
kill at the answer fired by `grab.py` when the reply area changed. The shell's Linux run is in
[the overlay runbook](../runbooks/body-overlay.md).

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
