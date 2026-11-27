# The deep tier never sends the template's preserve flag

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a multi-turn row on the deep pick in which the empty earlier thoughts change a deep reply.
**Verified:** 2026-11-27

The Qwen3.8 template reads `preserve_thinking`, on by default
([thinking-switch readings](../../readings/thinking-switch.md#the-effort-and-preserve-settings)).
On build b12375 the deep pick's `/props` reports `supports_preserve_reasoning`, and the server's
log at each start says preserving reasoning is on by default and names `--no-reasoning-preserve`.
No file under `brain/packages` or `docker` names the flag, so the deep tier runs with it on.

The brain keeps no reasoning with a stored reply. A render of a handoff's messages on the deep
server therefore puts an empty thought before each earlier reply
([readings](../../readings/model-swap.md#a-handoff-on-the-deep-pick)). No row says whether those
empty thoughts change the reply that follows them.

## Proposal

The flag stays out until a multi-turn row shows the empty earlier thoughts matter. Then the deep
tier's argv takes `--no-reasoning-preserve`.

**What closes it.** The row, and either the flag on the tier's argv with ADR-0004 decision 8
stating it, or a decline that states the row.

## History

- 2026-11-21: moved here from
  [R-738](738-the-deep-tier-cannot-set-a-templates-reasoning-effort-or-preserve-flag.md),
  which closed on the effort level and left the flag where it was.
- 2026-11-27: checked again and not fired: no reading committed since 2026-11-21 draws a multi-turn
  row on the empty earlier thoughts, and no file under `brain/packages` or `docker` names
  `--no-reasoning-preserve`.
