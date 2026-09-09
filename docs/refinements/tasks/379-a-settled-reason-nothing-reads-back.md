# A settled handoff's reason is written twice and read back by nothing

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-09
**Trigger:** a failed handoff whose reason nobody found in time, or any surface that starts
carrying handoff history. The second half is countable rather than felt:
`residency_probe.residency()` composes exactly two annotators through `residency_state.with_note`,
the missing peer and the spilled pace, and `HealthReply` in `proto/body.proto` carries `ready` and
`detail` and nothing else, so a third annotator or a wider reply is the event.
`grep -rn "with_note(" brain/packages` reports the first.

Opened 2026-08-22 by the close of
[R-350](350-a-failed-swap-in-says-nothing-brain-side.md), which gave a failed handoff a reason and
put it in the two places that outlive different things: one `WARNING` in the brain's log, and the
`failure` field on the record in Redis.

Neither is a surface anybody is looking at. The log line is found by an operator who is already
tailing the brain, or who knows the sentence to grep for; the record is found by somebody who
knows the key layout and asks Redis inside the diagnosis hour the adapter's TTL keeps a terminal
record for. Nothing in the tree reads `failure` back: the seam's residency report does not carry
it, the overlay never sees it, boot recovery does not read it, and no code path branches on it.
It is written for a human who has to know it is there.

That is defensible, and it is also the same gap the spill note closed for a related problem. A
handoff that decoded below its floor used to say so only in the brain's log, and the spill-note
addendum decided that was not a surface, so the verdict now travels on the residency report for an
hour and reaches an operator who is not tailing a container. A failed handoff's reason is the same
kind of fact one step further along: something about the last handoff, true for a bounded while,
that an operator would want without being told where to look.

**What is not the same, and is the argument against.** The user has already been told, in the
reply, what is true of their machine, and a failure they were told about does not obviously owe a
second telling on a health surface. A spill is the opposite case: nobody was told anything,
because the answer arrived and only its rate was wrong. So this may be right as it stands.

**What would close it.** Decide, rather than leaving it implied by the close that created it:
either put the last failed handoff's reason on a surface that reaches somebody (the residency
report is the precedent, with the same standing-and-lapsing rule), or record that the log line
plus the runbook's Redis recipe is deliberately the whole of it, and say why the spill note's
argument does not carry across. One paragraph either way; the field and its two writes stay.

**Re-derived on 2026-09-08, and every sentence above still holds.** `HandoffRecord.failure` is
declared once, carried through the one `HandoffStore.transition` signature, written by the settler
and by boot recovery through the two implementations of that method, and round-tripped by the
codec. Exactly one production line reads it,
[handoff_codec.py](../../../brain/packages/session/src/cortex_session/handoff_codec.py)'s encode,
and it reads it to write it back into redis. No code path branches on it, the seam is unchanged, and
`residency()` still joins the same two notes it joined in August.

One reading makes the display branch cheaper than the paragraphs above imply. The terminal record's
diagnosis TTL is 3600 seconds and the spill note's dwell is 3600.0 seconds, so a reason carried on
the residency report under the precedent's standing-and-lapsing rule would stand for exactly the
window the record already keeps it for, and the two copies would lapse together rather than one
outliving the other. That is an argument about cost and not about whether the surface is owed; the
question in the paragraph above, whether a failure the user was already told about owes a second
telling, is still the part that has to be decided rather than measured.

**Held to the code again on 2026-09-09, including the negative claim, which is the one that
matters here.** `with_note` still has exactly two callers in the brain's source,
`residency_pace.py` and `residency_tiers.py`; `HealthReply` in
[proto/body.proto](../../../proto/body.proto) is still `bool ready` and `string detail`; and
`record.failure` is still read by one production line, the codec's encode. The reason is the one
piece of handoff state here that does survive a model swap, since it rides the record in Redis
rather than any model's process, so what is missing is a reader and never durability. That is worth
saying plainly, because an entry about an unread field is easy to misread as an entry about a field
that gets lost.

## Trail

- 2026-08-22: opened by the close of
  [R-350](350-a-failed-swap-in-says-nothing-brain-side.md), which wrote the reason down in two
  places and found nothing that reads either of them.
- 2026-09-08: trigger checked and not fired, and the clause was narrowed to the two surfaces a
  reader can count. The readings: `with_note` has exactly two callers in the brain's source,
  `residency_tiers.StandingTiers.note_on` and `residency_pace.HandoffPace.note_on`, unchanged since
  the spill note landed; `HealthReply` still carries `ready` and `detail`; one production line reads
  `HandoffRecord.failure`, and it is the codec encoding it. Also recorded above: the record's
  diagnosis TTL and the spill note's dwell are the same hour, which is what the display branch would
  inherit.
- 2026-09-09: claims held to the code and all of them stand, the negative one included: two
  `with_note` callers, a two field `HealthReply`, and one production read of `record.failure`.
  Recorded above: the reason survives a swap on the record, so the gap is a reader. The trigger has
  not fired.
