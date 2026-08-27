# The hosted subagent tier meets the flag rule by hand rather than by the rule

**Status:** landed 2026-08-28
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-27 by the close of
[R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), which derived the set of
subagent servers a composed stack starts and held every one of them to the flags the tier requires.

`flagcheck.py` reads compose services, so the model host's own hosted subagent tier is out of its
reach by design: that tier is a child process the supervisor starts, and its argv is assembled in
`brain/packages/model_manager/src/cortex_model_manager/tiers.py` from `TierArgs`. It does carry all
three flags today, `_JINJA` for every tier and `_REASONING_OFF` on the subagent one, and the
model_manager roster suite pins that argv whole, so nothing is currently wrong. What is missing is
the same thing R-462 was filed for, one level down: **the sidecar's subagent tier is a position in
a fixed three-entry tuple, not a set anything reads**. A fourth tier added to `tiers()` for a
second subagent pick would carry whatever its author copied, and the suite pinning today's three
would go on passing for the three it names.

The two halves also spell one requirement twice. `flagcheck.REQUIREMENTS` says a subagent server
carries `--jinja` and the reasoning-off pair; `config.py` says it with `_JINJA` and
`_REASONING_OFF`. Only the budget's count is tied, by the constant registry.

**Why it was left.** The close it came out of had a compose reader to build and a gate to prove,
and this needs a different reader: the sidecar builds its argv in Python, so answering "which of
these tiers serves subagents" means reading a dataclass construction rather than a YAML block.
Building an unproven Python reader inside the pass that proved the compose one would have put the
two under one mutation table.

**What would close it.** Either a reading of the sidecar's own tiers that feeds the same
`REQUIREMENTS`, so one rule covers both placements of one tier, or the honest argument that the
model_manager suite is the right holder and what is owed instead is a check that every tier whose
id names a subagent carries `_REASONING_OFF`. The second is cheaper and should be argued against
before the first is built.

## Trail

- 2026-08-27: opened by the close of
  [R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), which reached every
  subagent server compose starts and left the one the supervisor starts to its own suite.
- 2026-08-28: landed as the
  [ADR-0029 addendum on one rule over both placements of one tier](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-08-28-one-rule-over-both-placements-of-one-tier-since-a-reader-is-not-a-claim),
  a second member source for the same rule: `scripts/hostedtiers.py` reads the sidecar's own tier
  declarations and `scripts/moduleconstants.py` is the syntax under it, and `scripts/flagcheck.py`
  runs `REQUIREMENTS` over the union of that and the compose set. **Re-derivation found nothing
  stale**, every claim this entry made held, though "pins that argv whole" was generous: the
  model_manager suite pins the cortex tier's argv flag for flag and the subagent tier's tail.
  **The cheap close was argued and refused.** It runs the real code, which is its real advantage,
  and its membership test could have been derived honestly from `model_fields` rather than from a
  renameable id. It was refused on one scenario that is the entry's own point: `REQUIREMENTS` is
  data, so a fourth flag is a line, and a suite in another tree cannot be reached by that line.
  The two halves are complementary rather than redundant, measured in the addendum's table: that
  suite says what the tier really starts with and the gate says the rule reaches it. **The rest of
  the requirement is tied by the rule rather than by the registry**, the gate now comparing the
  sidecar's own `_JINJA` and `_REASONING_OFF` against `REQUIREMENTS` in both directions, which a
  value coupling could not have done for the pair. The registry's entry stays for the runbook's
  hand-started server, which no rule reaches. What the close opened is the convention underneath
  both readers,
  [R-472](472-the-membership-prefix-is-a-convention-nothing-enforces.md).
