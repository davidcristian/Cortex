# The hosted subagent tier meets the flag rule by hand

**Status:** done 2026-08-28
**Area:** repo-checks
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)

`flagcheck.py` reads compose services, so the model host's own hosted subagent tier is outside it:
that tier is a child process the supervisor starts, and its argv is assembled in
`brain/packages/model_manager/src/cortex_model_manager/tiers.py` from `TierArgs`. It uses all three
flags today, `_JINJA` for every tier and `_REASONING_OFF` on the subagent one, and the
model_manager roster suite asserts that argv, so nothing was wrong. What was missing is the same
thing [R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md) was filed for, one
level down: the sidecar's subagent tier is a position in a fixed three-entry tuple, not a set
anything reads. A fourth tier added to `tiers()` for a second subagent pick would use whatever its
author copied, and the suite would go on passing for the three it names.

The two halves also write one requirement twice. `flagcheck.REQUIREMENTS` says a subagent server
uses `--jinja` and the reasoning-off pair; `config.py` says it with `_JINJA` and `_REASONING_OFF`.
Only the budget's count was compared, by the constant registry.

## History

- 2026-08-27: opened by the close of
  [R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), which reached every
  subagent server compose starts and left the one the supervisor starts to its own suite.
- 2026-08-28: closed as the rule over both placements of one tier in
  [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md), a second member source for the same rule:
  `scripts/hostedtiers.py` reads the sidecar's own tier declarations, `scripts/moduleconstants.py`
  is the syntax reader under it, and `scripts/flagcheck.py` runs `REQUIREMENTS` over the union of
  that and the compose set. Every claim this entry made held, though the model_manager suite
  asserts the cortex tier's argv flag for flag and the subagent tier's tail rather than each whole
  argv. The cheaper close, a test that every tier whose id names a subagent uses `_REASONING_OFF`,
  was rejected on the entry's own point: `REQUIREMENTS` is data, so a fourth flag is one line here
  and a suite in another tree cannot be reached by that line. The two halves are complementary,
  measured in the record's table: the suite says what the tier really starts with and the check says
  the rule reaches it. The check now compares the sidecar's `_JINJA` and `_REASONING_OFF` against
  `REQUIREMENTS` in both directions, which a value coupling could not have done for the pair, and
  the registry entry stays for the runbook's hand-started server. Opened by it:
  [R-472](472-the-membership-prefix-is-a-convention-nothing-enforces.md).
