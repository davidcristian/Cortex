# The subagent tier's reasoning-off flags are spelled in three files and held together by nobody

**Status:** open, actionable
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
it reddens on a violation. Adding it in the same pass would have been the gate landing untested
beside the fix it was meant to hold.

**What would close it.** A coupling in `subagentcouplings.py`, which already holds this tier's
budgets, tying the flag pair as a value across the three files, so a server started without it is a
red rather than a slow subagent. The reading it has to survive is that two of the three spellings
are YAML list items and the third a Python tuple, which is the "second spelling a far side's own
syntax forces" case the cross-language addendum already covers.
