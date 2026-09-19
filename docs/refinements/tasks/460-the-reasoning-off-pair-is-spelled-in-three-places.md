# The subagent tier's reasoning-off flags are written in three files and checked by nobody

**Status:** done 2026-08-26
**Area:** repo-checks
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)

Every subagent server this repo ships must start with both `--chat-template-kwargs
'{"enable_thinking": false}'` and `--reasoning-budget 0`, because neither alone covers both model
families. The pair is written out three times: in `docker/docker-compose.subagents.yml`, in
`docker/docker-compose.subagents-roster.yml`, and as `_REASONING_OFF` in the model host's
`config.py` for the hosted GPU tier. Nothing compared them. A fourth subagent server, or an edit
that fixed one file and not the others, would ship a tier with a reasoning trace running on every
constrained reply, whose only symptom is a slow refusal.

The fix is an entry in `scripts/subagentcouplings.py`, which already covers this tier's budgets,
comparing the flag pair as a value across the files that write it.

## History

- 2026-08-26: opened by the close of
  [R-456](456-a-constrained-request-loses-the-thinking-lever.md), which added a second flag to each
  of the three copies and left the check for its own pass.
- 2026-08-26: closed as one registry entry in `scripts/subagentcouplings.py` with one site and two
  mentions, since replaced by the derived set of
  [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md). No new vocabulary was needed: a mention
  is a value plus a shape, so the budget's count is the value and the two flag names and the
  kwarg's JSON are the shape, which makes half a pair a missing entry. Checking the premise moved
  it once: the third copy is already asserted whole by the model_manager roster suite, so the
  registry entry covers the two compose files and says so. The count was hoisted out of
  `_REASONING_OFF` into `_NO_REASONING_BUDGET` to be readable at all. What the entry did not get is
  the general claim that every subagent server this repo starts uses the pair, because nothing
  enumerates that set; that is
  [R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), filed beside
  [R-463](463-the-subagent-couplings-part-is-two-lines-under-the-cap.md) for the part file this
  entry pushed to within two lines of the cap.
