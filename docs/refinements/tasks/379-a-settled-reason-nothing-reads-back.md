# A settled handoff's reason is written twice and read back by nothing

**Status:** declined 2026-09-15
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

A failed handoff's reason is written in two places that outlive different things: one `WARNING` in
the brain's log, and the `failure` field on the record in Redis.

Neither is a surface anybody is looking at. The log line is found by an operator who is already
tailing the brain, or who knows the sentence to grep for; the record is found by somebody who knows
the key layout and asks Redis inside the hour the adapter's TTL keeps a terminal record for.
Nothing in the tree reads `failure` back: the residency report does not include it, the overlay
never sees it, boot recovery does not read it, and no code path branches on it.

That is defensible, and it is also the gap the spill note closed for a related problem. A handoff
that decoded below its floor used to say so only in the brain's log, and the spill note's decision
(ADR-0055 decision 5) judged that was not a surface, so the result now travels on the residency
report for an hour. A failed handoff's reason is the same kind of fact one step further along.

The argument against is that the user has already been told, in the reply, what is true of their
machine, while a spill is the opposite case, nobody having been told anything because the answer
arrived and only its rate was wrong.

One reading makes the display option cheaper than that implies. The terminal record's diagnosis TTL
is 3600 seconds and the spill note's dwell is 3600.0 seconds, so a reason on the residency report
under the same rule would last exactly the window the record already keeps it for, and the two
copies would expire together.

## History

- 2026-08-22: Opened by the close of [R-350](350-a-failed-swap-in-says-nothing-brain-side.md),
  which wrote the reason down in two places and found nothing that reads either of them.
- 2026-09-08: Trigger checked and not fired, and narrowed to the two surfaces a reader can count.
  `with_note` has exactly two callers in the brain's source,
  `residency_tiers.StandingTiers.note_on` and `residency_pace.HandoffPace.note_on`, unchanged since
  the spill note; `HealthReply` still has `ready` and `detail`; one production line reads
  `HandoffRecord.failure`, and it is the codec encoding it. Also recorded above: the record's
  diagnosis TTL and the spill note's dwell are the same hour.
- 2026-09-09: Claims checked against the code and all stand, the negative one included: two
  `with_note` callers, a two field `HealthReply`, and one production read of `record.failure`. The
  reason survives a swap on the record in Redis, so what is missing is a reader and never
  durability, which is worth saying plainly because an entry about an unread field is easy to
  misread as one about a field that gets lost. The trigger has not fired.
- 2026-09-13: The three countable claims were read again and all stand. `with_note` still has
  exactly two callers, `residency_pace.py` and `residency_tiers.py`; `HealthReply` in
  [proto/body.proto](../../../proto/body.proto) is still `bool ready` and `string detail`; and
  `record.failure` is still read by one production line,
  [handoff_codec.py](../../../brain/packages/session/src/cortex_session/handoff_codec.py)'s encode.
- 2026-09-15: Declined, which is the half of "one paragraph either way" this entry left to be
  chosen. The three countable claims were checked once more and all stand. What settled the
  question was a fourth reading nobody had taken, that `with_note` annotates a serving report and
  hands a non-serving one straight back, which inverts the proposed surface: it would show the
  reason where the machine is already fine and drop it on the two states whose reason is worth
  having, a restore that stopped retrying publishing `RESIDENCY_LOST` and a boot that could not
  confirm the cortex publishing `RESIDENCY_BOOT_FAILED`. Putting it on the non-serving report
  instead is ruled out by who reads that string: `ResidencyReport.detail` is rendered word for word
  to the user by [linkState.ts](../../../body/app/src/overlay/linkState.ts), and two of the reasons
  are the message of the error that ended the sequence, which is where the model host's status code
  and body excerpt reach the brain. ADR-0030 decisions 6 and 10 state that the user is owed what is
  true of their machine and not that status. The spill note's argument does not transfer for a
  sharper reason than "the user was told": `SPILLED_PACE_DETAIL` says what the next deep task will
  do, so it stays true until the card has room, and none of the five reasons says anything about
  the next handoff. The log line plus the runbook's Redis recipe is recorded as deliberately the
  whole of it, in [docs/runbooks/model-swap.md](../../runbooks/model-swap.md) and in ADR-0030
  decision 10. No code changed. The counting half of the same question stays with
  [R-321](321-a-spill-nobody-saw-is-forgotten.md), and the width of the one detail string with
  [R-320](320-one-detail-string-two-facts.md).
