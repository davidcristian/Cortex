# The subagent tier's reasoning-off flags are spelled in three files and held together by nobody

**Status:** landed 2026-08-26
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-26 by the close of
[R-456](456-a-constrained-request-loses-the-thinking-lever.md), which added a second flag to each
of the three spellings.

Every subagent server this repo ships must start with both `--chat-template-kwargs
'{"enable_thinking": false}'` and `--reasoning-budget 0`, because neither alone covers both lineup
families. The pair is written out three times: in `docker/docker-compose.subagents.yml`, in
`docker/docker-compose.subagents-roster.yml`, and as `_REASONING_OFF` in the model host's
`config.py` for the hosted GPU tier. Nothing ties them. A deployment that gained a fourth subagent
server, or an edit that fixed one file and not the others, would ship a tier with a reasoning trace
running on every constrained reply, which is a defect whose only symptom is a slow refusal.

**Why it was left.** The entry that added the flag had a live measurement to take and a deadline,
and a new coupling in `scripts/crosscheck.py` is a gate change, which owes a mutation table proving
it fails on a violation. Adding it in the same pass would have been the gate landing untested
beside the fix it was meant to hold.

**What would close it.** A coupling in `subagentcouplings.py`, which already holds this tier's
budgets, tying the flag pair as a value across the three files, so a server started without it
fails the gate rather than producing a slow subagent. The reading it has to survive is that two of the three spellings
are YAML list items and the third a Python tuple, which is the "second spelling a far side's own
syntax forces" case the cross-language addendum already covers.

## Trail

- 2026-08-26: opened by the close of
  [R-456](456-a-constrained-request-loses-the-thinking-lever.md), which added a second flag to
  each of the three spellings and left a gate change for its own pass.
- 2026-08-26: landed as the
  [ADR-0029 addendum on holding a flag pair as one needle](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-08-26-two-flags-that-must-travel-together-are-one-needle-not-a-new-relation),
  one entry in `scripts/subagentcouplings.py` with one site and two mentions. The co-occurrence
  needed no new vocabulary: a mention is a value plus shape, so the budget's count is the value
  and the two flag names and the kwarg's own JSON are the shape, which makes half a pair an
  unfound needle. **Re-derivation moved the entry's premise once.** The three spellings were
  where it said they were, but the third is already pinned whole by the model_manager roster
  suite, so the coupling holds the two compose files and says so. The count had to be hoisted out
  of `_REASONING_OFF` into `_NO_REASONING_BUDGET` to be readable at all, which is the price this
  module's tier defaults have paid before. What the entry hoped for and did not get is the
  durable claim, that every subagent server this repo starts carries the pair; that set is
  enumerated by nobody, which is filed as
  [R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), beside the part file
  the entry pushed to within two lines of the cap,
  [R-463](463-the-subagent-couplings-part-is-two-lines-under-the-cap.md).
