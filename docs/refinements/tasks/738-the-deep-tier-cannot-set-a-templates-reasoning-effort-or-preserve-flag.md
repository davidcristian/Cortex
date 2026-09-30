# The deep tier cannot set a template's reasoning effort or preserve flag

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** ADR-0004 names a Qwen3.8 artifact as a pick or alternate for any tier, or the maintainer
picks the step two names below.
**Verified:** 2026-09-30

The Qwen3.8 template reads `reasoning_effort` (`xhigh` by default, `high` rendered as `xhigh`,
`medium`, `low`; any other value raises with thinking on) and `preserve_thinking` (on by default).
The deep tier sends neither, so a Qwen3.8 deep tier runs at `xhigh`. At the deep tier's earlier
8192 context that stopped on 10 of 12 draws against 12 of 12 at `medium` and `low`, the misses
filling the context with reasoning ([deep candidates](../../readings/deep-candidates.md)). No
Qwen3.8 draw was taken at the shipped 16384, where the pick's one miss at 8192 reasoned 418 tokens
further and replied
([deep tier at 16384](../../readings/history-window.md#the-deep-tier-at-16384)).

No shipped pick or alternate reads the effort: the gemma, Qwen3.5 and Qwen3.6 templates render every
value the same as none ([thinking-switch readings](../../readings/thinking-switch.md#the-effort-and-preserve-settings)).
On them depth is set only by the thinking switch and the trace budget.

## Proposal

**Step one, a default level for the deep tier.** `GenerationBounds` gains an optional core level of
three, sent by `build_payload` as the request field `reasoning_effort` (`low`, `medium`, `high`),
never a value the template raises on. The adapter checks the leased server's
`chat_template_caps.supports_reasoning_effort` in `GET /props` and drops the field with a warning
where it is false, caching nothing, as ADR-0071 decision 3 does. The default is a brain setting
validated at wiring, so a typo fails the start, not every handoff; nothing is held by a model
server, so a swap changes nothing. Recommended for a Qwen3.8 deep tier: `medium`. The model host's
`--reasoning-effort` flag is rejected: it passes any value unchecked and a bad one fails every reply
while the tier reports ready. The preserve flag stays out until a multi-turn row shows the empty
earlier thoughts matter; then the argv takes `--no-reasoning-preserve`.

**Step two, optional: one user preference.** One level for every turn, written with `SetPreference`
and read by the brain, which changes ADR-0032's rule that the brain never parses a preference, and
hidden where the serving model has no effort setting, which today is every shipped pick. It is not
a per-message control, because the deep handoff's confirm card already asks mid-turn whether to
think harder. Names await the maintainer's pick: **Wade, Swim, Dive** (recommended; the overlay's
surfaces are water already), or Stroll, Hike, Trek, or Presto, Andante, Largo; key `reply.effort`.

**What closes it.** Step one built once the trigger fires, with the deep injection row drawn at the
chosen level (the 2026-09-26 row ran at `xhigh`). Declined if ADR-0004 drops both Qwen3.8 candidates
and the maintainer declines step two.

## History

- 2026-09-26: filed by the deep candidates' measurement.
- 2026-09-30: not fired: ADR-0004 decision 8 names gemma-4-31B as the deep pick and Qwen3.6-27B
  as its alternate, and no tier's decision names a Qwen3.8 artifact. The deep tier now starts at
  16384, so the body marks the stop counts as drawn at 8192.
