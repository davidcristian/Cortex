# Prefill as the second sign of a spill

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)
**Verified:** 2026-09-19
**Trigger:** A spill that decode misses, or a deployment whose deep answers are short enough that decode rarely clears `MIN_CADENCE_TOKENS`, which reads in the log as successful handoffs that mostly write the deep phase's no-decode-rate INFO line rather than its decode-rate line.

llama.cpp's `timings` object reports `prompt_per_second` beside the decode rate, and the
co-residency run recorded it collapsing to 13.8 tok/s on the first request after a switch, where a
fitting pair holds 105 to 134 ([model-swap.md](../../runbooks/model-swap.md)). That is a sharper
contrast than decode's. It was left out because prompt rate varies with prompt length far more
than decode does, so the floor a deployment would have to measure is a harder number and a wrongly
set one produces false collapses.

**The field costs nothing extra to read.** The adapter takes `predicted_per_second` and
`predicted_n` from the same `timings` object
([decode.py](../../../brain/packages/inference/src/cortex_inference/decode.py)) and reads nothing
else there. The contract suite has recorded the object whole since 2026-08-08: `_TIMINGS` in
`brain/packages/inference/tests/test_cadence_contract.py` is the final chunk of a streaming body
and includes `cache_n`, `prompt_n`, `prompt_ms`, `prompt_per_token_ms` and `prompt_per_second`
beside the four predicted fields. A live check on build `b10680-d7bd3bfca` confirmed the same
fields in the final streamed chunk of a `/v1/chat/completions` request. So a second instrument
needs no extra request and no second parse.

**The calibration objection is stronger than it looked, measured 2026-09-15.** `--cache-ram` sizes
the prompt cache llama.cpp keeps in host RAM for a conversation whose slot has been taken
([config.py](../../../brain/packages/model_manager/src/cortex_model_manager/config.py)), and it
does not govern the in-slot prefix reuse a request gets when it extends the prompt the same slot
just answered. A CPU server started with `--cache-ram 0`, the deep tier's shipped setting,
reported `cache_n` 0 and `prompt_n` 21 on a cold request, and `cache_n` 17 and `prompt_n` 4 on
each repeat. The deep phase runs a whole tool loop under one handoff
([brain_phase.py](../../../brain/packages/core/src/cortex_core/brain_phase.py)), so its second and
later completions are exactly the reused-prefix case.

`prompt_per_second` is `prompt_n` over `prompt_ms`, so a mostly cached prompt divides one
request's fixed cost by very few processed tokens and reads slower rather than faster. On that
probe the cold request reported 12.3 tokens per second and its own repeats 4.5 and 4.8, a factor
of 2.6 with nothing about the card changed; a second server at the engine's default cache size
gave 9.5 against 4.3 and 4.4. So the false collapse is produced by the cheapest requests rather
than by a loaded card, and a prefill watch would need a minimum processed-prompt length as well as
a floor, where decode needs one number that is already chosen (`MIN_CADENCE_TOKENS`, 32). The
existing watch's shape would absorb it if that minimum were read off `prompt_n` rather than off
the prompt's length. The readings are in [co-residency](../../readings/co-residency.md); no GPU
was used, so they are quoted only as ratios of their own server's numbers.

## History

- 2026-08-08: Opened behind the spill watch, prefill declined there with its reason: the prompt
  rate collapsed harder than decode did on the co-residency run, but it varies with prompt length
  far more, so one instrument that works beats two that need calibrating.
- 2026-08-09: A trigger review of the index's fix-when-it-matters bucket read it against the tree
  and fired nothing. This entry got that result inside a group rather than under its own name.
- 2026-09-09: Claims checked against the code, and the one the tree could not answer checked
  against a live server. `MIN_CADENCE_TOKENS` is 32, `DecodeCadence` is still filled from the same
  `timings` object, the runbook still records the 13.8 against 105 to 134 contrast, and `timings`
  really does report `prompt_per_second`. The trigger has not fired.
- 2026-09-13: Claims checked again and all held. Recorded then: every tier now states its own
  `--cache-ram` and the deep tier states zero, which looked like it removed the cache-restore half
  of the variance on the tier this would be read on. The trigger has not fired.
- 2026-09-15: Checked against a live CPU server, which corrected the entry. The cost claim is
  confirmed on the streaming path the adapter uses. The 2026-09-13 narrowing is withdrawn, with
  the numbers above. The entry stays open and its decline rests on better evidence than before.
- 2026-09-19: Claims checked, and one negative claim was wrong from the day it was written. The
  2026-09-09 paragraph said no fixture in `cortex_inference`'s suite held more than the two decode
  keys; `_TIMINGS` has held all nine fields of a streamed final chunk since 2026-08-08, and
  `test_backend.py`'s `_timings` builds `cache_n` and `prompt_n` into every case. The paragraph
  now says so. The trigger's second half now names the log line that shows it, since the deep
  phase writes its no-decode-rate INFO line for an answer shorter than `MIN_CADENCE_TOKENS`. The
  rename of the decode-rate log fields on 2026-09-17 touched neither rate's source. The trigger
  has not fired.
