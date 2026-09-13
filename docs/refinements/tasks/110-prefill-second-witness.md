# Prefill as the second witness of a spill

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-13
**Trigger:** A spill that decode misses, or a deployment whose deep answers are short enough that decode rarely clears `MIN_CADENCE_TOKENS`.

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

**The field this entry names was read off a live server on 2026-09-09.** Nothing in the tree
records llama.cpp's `timings` object whole: the adapter takes `predicted_per_second` and
`predicted_n` from it
([decode.py](../../../brain/packages/inference/src/cortex_inference/decode.py)) and every fixture
in `cortex_inference`'s suite builds those two keys and no others, so the claim that a prompt rate
arrives beside the decode rate is a claim about the server rather than about this repo. A CPU
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
