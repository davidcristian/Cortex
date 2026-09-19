# Prefill as the second witness of a spill

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-19
**Trigger:** A spill that decode misses, or a deployment whose deep answers are short enough that decode rarely clears `MIN_CADENCE_TOKENS`, which reads in the log as successful handoffs that mostly write the deep phase's no-decode-rate INFO line rather than its decode-rate line.

Opened 2026-08-08 by
the same landing. `timings` carries `prompt_per_second` beside the decode rate, and the
co-residency run recorded it collapsing to 13.8 tok/s on the first request after a switch where a
fitting pair holds 105 to 134 ([model-swap.md](../../runbooks/model-swap.md)), which is a sharper
contrast than decode's. It was left out because prompt rate varies with prompt length far more
than decode does, so the floor a deployment would have to measure is a harder number and a
wrongly set one produces false collapses; one instrument that works beats two that need
calibrating. The arm is already shaped to carry it, `DecodeCadence` being a value the adapter
fills from the same object. **Trigger:** a spill that decode misses, or a deployment whose deep
answers are short enough that decode rarely clears `MIN_CADENCE_TOKENS`.

**The field this entry names was read off a live server on 2026-09-09, and the tree already held
a copy of it.** The adapter takes `predicted_per_second` and `predicted_n` from llama.cpp's
`timings` object ([decode.py](../../../brain/packages/inference/src/cortex_inference/decode.py))
and reads nothing else there. The contract suite has recorded the object whole since the landing
that opened this entry: `_TIMINGS` in `brain/packages/inference/tests/test_cadence_contract.py` is
the final chunk of a streaming body, described there as verbatim in shape from a live run, and it
carries `cache_n`, `prompt_n`, `prompt_ms`, `prompt_per_token_ms` and `prompt_per_second` beside
the four predicted fields. So a prompt rate arriving beside the decode rate is a fact about the
server that this repo's own fixture had written down, not one it lacked. A CPU
llama-server on build 10680 answered an eight token completion with nine timing fields, among them
`prompt_n`, `prompt_ms`, `prompt_per_token_ms` and `prompt_per_second`. The second instrument
therefore costs no extra request and no second parse, only another read of the object the adapter
already holds, which leaves the calibration argument above as the whole of the case against it.
Nothing here touches the rule that state must survive a model swap: both rates are readings taken
after a swap has finished, and a rate is not state anything could lose.

**The tier this instrument would be read on has since been given a prompt cache size of its own,
read 2026-09-13.** Every model-host tier now states `--cache-ram` rather than taking the engine's
8192 MiB default ([config.py](../../../brain/packages/model_manager/src/cortex_model_manager/config.py)),
and the deep tier states zero while the cortex states 8192. That narrows the calibration argument
on the one tier this would run against: `CadenceWatch` is wired by the deep phase
([brain_phase.py](../../../brain/packages/core/src/cortex_core/brain_phase.py)), the deep tier
restores no conversation, so a prompt rate read there is always a cold one and cannot swing
between a restored request and a cold one. Prompt length is still the variance the original
argument named, and on that tier it is now the only one. The cortex is the opposite case, a
restored return costing 1.9 s against 3.5 s of cold prompt eval, so a single prefill floor set for
every tier would have been wrong there.

**That narrowing does not hold, and the reading that removes it was taken live on 2026-09-15.**
`--cache-ram` sizes the prompt cache llama.cpp keeps in host RAM for a conversation whose slot has
been taken ([config.py](../../../brain/packages/model_manager/src/cortex_model_manager/config.py)),
and it does not govern the in-slot prefix reuse a request gets when it extends the prompt the same
slot just answered. A CPU server started with `--cache-ram 0`, which is the deep tier's shipped
setting, reported `cache_n` 0 and `prompt_n` 21 on a cold request and `cache_n` 17 and `prompt_n` 4
on each repeat of the same question. The deep phase runs a whole tool loop under one handoff
([brain_phase.py](../../../brain/packages/core/src/cortex_core/brain_phase.py)), so its second and
later completions are exactly the reused-prefix case, and a prompt rate read on that tier is a cold
one only for the first of them.

**What that costs the instrument, as a number.** `prompt_per_second` is `prompt_n` over
`prompt_ms`, so a mostly cached prompt divides one request's fixed cost by very few processed
tokens and reads slower rather than faster: on the probe above the cold request reported 12.3
tokens per second and its own repeats 4.5 and 4.8, a factor of 2.6 on one server, one model and one
prompt with nothing about the card changed. A second server at the engine's default cache size gave
9.5 against 4.3 and 4.4. So the false collapse this entry was declined for is real, it is produced
by the cheapest requests rather than by a loaded card, and a prefill watch would need a minimum
processed-prompt length as well as a floor, where decode needs one number that is already chosen
and argued (`MIN_CADENCE_TOKENS`). The existing watch's shape would absorb it if that minimum were
read off `prompt_n` rather than off the prompt's length, which is the design question a landing
would start from.

**The cost claim itself is confirmed on the path the adapter actually uses.** The 2026-09-09
reading was taken on a completion this entry does not record as streamed, and the adapter only ever
streams, though the contract fixture named above was already a streamed chunk. The final streamed chunk of a `/v1/chat/completions` request on build `b10680-d7bd3bfca`
carries `prompt_n`, `prompt_ms`, `prompt_per_token_ms`, `prompt_per_second` and `cache_n` in the
same `timings` object `_cadence` already reads `predicted_per_second` out of, so the second
instrument really does cost no extra request and no second parse. No GPU was used, so the figures
above describe a CPU probe and are quoted only as ratios of their own server's readings.

## Trail

- 2026-08-08: Opened behind the same landing, prefill declined there as a second instrument with
  its reason rather than merely left unread: the `timings` object already carries the prompt rate
  and it collapsed harder than decode did on the co-residency run, but a prompt rate varies with
  prompt length far more than decode does, so the floor a deployment must measure is a harder
  number whose wrong setting produces false collapses, and one instrument that works beats two
  that need calibrating.
- 2026-08-09: A trigger sweep of the index's fix-when-it-bites bucket read that bucket against the
  tree and fired nothing. This entry reached that verdict inside a group rather than under its own
  name, the residency and model-manager entries each recent close opened, whose triggers are
  live-observation shaped, a deployment doing something rather than a file saying something, so no
  reading of the code settles them.
- 2026-09-09: claims held to the code, and the one this tree cannot answer held to a live server.
  `MIN_CADENCE_TOKENS` is 32, `DecodeCadence` is still filled from the same `timings` object a
  prompt rate rides on, and the runbook still records the 13.8 against 105 to 134 contrast. The
  live reading, recorded above, is that `timings` really does carry `prompt_per_second`. The
  trigger has not fired.
- 2026-09-13: claims held to the code again and all of them stand. `MIN_CADENCE_TOKENS` is 32,
  `_cadence` in [decode.py](../../../brain/packages/inference/src/cortex_inference/decode.py) still
  takes `predicted_per_second` and `predicted_n` off the same `timings` object a prompt rate rides
  on, and the runbook still records the 13.8 against 105 to 134 contrast, which it names as
  prefill. Recorded above: every tier now states its own `--cache-ram` and the deep tier states
  zero, which removes the cache-restore half of the variance on the tier this instrument would be
  read on. The trigger has not fired.
- 2026-09-15: claims held to the code and the two the tree cannot answer held to a live CPU server,
  which corrected the entry rather than confirming it. The cost claim is confirmed on the streaming
  path the adapter uses: the prompt fields ride the same `timings` object as the decode rate. The
  2026-09-13 narrowing is withdrawn: `--cache-ram 0` does not make the deep tier's prompt rate a
  cold reading, because it does not govern in-slot prefix reuse and a deep phase's tool loop runs
  several completions under one handoff. Recorded above with its numbers: a cached prompt reads 2.6
  times slower than a cold one on the same server, so the false collapse is produced by the
  cheapest requests, and a prefill watch needs a minimum processed-prompt length as well as a
  floor. The entry stays open and the decline it records stands on better evidence than it had.
  The readings are in the ADR-0030 addendum of that date.
- 2026-09-19: claims held to the code, and one negative claim was wrong from the day it was
  written. `MIN_CADENCE_TOKENS` is still 32 in `cortex_core/cadence.py`, `_cadence` still takes
  `predicted_per_second` and `predicted_n` and nothing else, `CadenceWatch` is still built by the
  deep phase, every model-host tier still states `--cache-ram`, and the runbook still records the
  13.8 against 105 to 134 contrast. The 2026-09-09 paragraph said no fixture in
  `cortex_inference`'s suite carries more than the two decode keys; the contract suite's
  `_TIMINGS` has carried all nine fields of a streamed final chunk since 2026-08-08, and
  `test_backend.py`'s `_timings` builds `cache_n` and `prompt_n` into every case. The paragraph now
  says so. The trigger's second half now names the log line that shows it, since the deep phase
  writes its no-decode-rate INFO line for an answer shorter than `MIN_CADENCE_TOKENS`. The
  rename of the decode-rate log fields on 2026-09-17 touched neither rate's source. The trigger has
  not fired.
