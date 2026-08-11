# Prefill as the second witness of a spill

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
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
