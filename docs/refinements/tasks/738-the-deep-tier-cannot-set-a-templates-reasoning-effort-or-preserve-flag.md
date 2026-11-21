# The deep tier cannot set a template's reasoning effort or preserve flag

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-21

The Qwen3.8 template reads `reasoning_effort` (`xhigh` by default, `high` rendered as `xhigh`,
`medium`, `low`; any other value raises with thinking on) and `preserve_thinking` (on by default).
The deep tier sends neither, so the deep pick, Qwen3.8-27B (ADR-0004 decision 8), runs at `xhigh`,
which is not its best measured setting. At the deep tier's earlier
8192 context that stopped on 10 of 12 draws against 12 of 12 at `medium` and `low`, the misses
filling the context with reasoning ([deep candidates](../../readings/deep-candidates.md)). At
the shipped 16384 it stopped on 11 of 12 without a drafter and 12 of 12 with its draft layer, at
a median of 2327 and 2883.5 reasoning tokens a draw, and at `medium` on 12 of 12 at a median of
1182.5 ([the stop rows at 16384](../../readings/deep-candidates.md#the-stop-rows-at-16384)).

Only the Qwen3.8 template reads the effort: the gemma, Qwen3.5 and Qwen3.6 templates render every
value the same as none ([thinking-switch readings](../../readings/thinking-switch.md#the-effort-and-preserve-settings)).
On them depth is set only by the thinking switch and the trace budget.

## Proposal

**Step one, a default level for the deep tier.** `GenerationBounds` gains an optional core level of
three, sent by `build_payload` as the request field `reasoning_effort` (`low`, `medium`, `high`),
never a value the template raises on. The adapter checks the leased server's
`chat_template_caps.supports_reasoning_effort` in `GET /props` and drops the field with a warning
where it is false, caching nothing, as ADR-0071 decision 3 does. The model host's b11312 build
has the capability and both flags; the effort readings were rendered on b10680. The default is a brain setting
validated at wiring, so a typo fails the start, not every handoff; nothing is held by a model
server, so a swap changes nothing. Recommended for a Qwen3.8 deep tier: `medium`. The model host's
`--reasoning-effort` flag is rejected: it passes any value unchecked and a bad one fails every reply
while the tier reports ready. The preserve flag stays out until a multi-turn row shows the empty
earlier thoughts matter; then the argv takes `--no-reasoning-preserve`.

**Step two, optional: one user preference.** One level for every turn, written with `SetPreference`
and read by the brain, which changes ADR-0032's rule that the brain never parses a preference, and
hidden where the serving model has no effort setting, which today is every pick but the deep one. It is not
a per-message control, because the deep handoff's confirm card already asks mid-turn whether to
think harder. Names await the maintainer's pick: **Wade, Swim, Dive** (recommended; the overlay's
surfaces are water already), or Stroll, Hike, Trek, or Presto, Andante, Largo; key `reply.effort`.

**What closes it.** Step one built, with the deep injection row drawn at the
chosen level (the 2026-09-26 row ran at `xhigh`). Declined if ADR-0004 drops both Qwen3.8 candidates
and the maintainer declines step two.

## History

- 2026-09-26: filed by the deep candidates' measurement.
- 2026-09-30: not fired: ADR-0004 decision 8 names gemma-4-31B as the deep pick and Qwen3.6-27B
  as its alternate, and no tier's decision names a Qwen3.8 artifact. The deep tier now starts at
  16384, so the body marks the stop counts as drawn at 8192.
- 2026-10-04: not fired: decision 8 names gemma-4-31B and Qwen3.6-27B, and decision 5 lists the
  two Qwen3.8 files as candidates only. A third Qwen3.8-27B file, a `llmfan46/` repackage with its
  own template, is on the mount since 2026-09-30 and is no candidate. The model host image is now
  b11312: its `--help` lists `--reasoning-effort` and `--no-reasoning-preserve`, and its binary
  holds `supports_reasoning_effort`, so the proposal is still writable.
- 2026-10-25: checked again and not fired: the deep row of ADR-0004 is unchanged, and
  `GenerationBounds` still has no effort field.
- 2026-11-10: checked again and not fired: ADR-0004 has no commit since 2026-10-25 and lists the
  Qwen3.8 artifacts as candidates only, no pick is recorded here, and `GenerationBounds` still has
  no effort field.
- 2026-11-16: fired: ADR-0004 decision 8 names Qwen3.8-27B as the deep alternate, since the
  models mount no longer holds Qwen3.6-27B. Nothing named here is built yet.
- 2026-11-20: ADR-0004 decision 8 now names Qwen3.8-27B as the deep pick, so this task blocks
  the pick's best setting: at `xhigh`, which the tier runs, it stopped on 10 of 12 draws at 8192,
  and at `medium` and `low` on 12 of 12. `GenerationBounds` still has no effort field.
  Filed: [R-1266](1266-qwen38-27b-has-no-stop-row-at-the-shipped-16384-context.md) for the stop row at 16384 and
  [R-1267](1267-qwen38-27bs-injection-row-was-drawn-at-8192-on-an-earlier-build.md) for the injection row.
- 2026-11-21: checked against the tree and the model host's b12375 build. No file under
  `brain/packages` names `reasoning_effort` or `preserve_thinking`. `/props` of the deep server
  on Qwen3.8-27B reports `supports_reasoning_effort` with the levels `low`, `medium` and `xhigh`
  and `supports_preserve_reasoning`, and its log at each start says preserving reasoning is on by
  default and names `--no-reasoning-preserve`. Two handoffs through the brain at `xhigh` ended on
  their own after 878 and 103 decoded tokens, and a render of the handoff's messages on that
  server puts an empty thought before each earlier reply
  ([readings](../../readings/model-swap.md#a-handoff-on-the-deep-pick)). The proposal is
  unchanged.
- 2026-11-21: the stop rows at 16384 are this task's evidence
  ([readings](../../readings/deep-candidates.md#the-stop-rows-at-16384)). `reasoning_effort` as
  a request field changes the render on b12375, and `chat_template_kwargs` renders the same
  bytes. Without a drafter `medium` stopped on 12 of 12 at a median of 1182.5 reasoning tokens,
  against 11 of 12 and 2327 at `xhigh`; the one `xhigh` miss spent the whole context. With the
  draft layer `low` stopped on 12 of 12 at 1415.5 and `xhigh` on 12 of 12 at 2883.5. One `medium`
  draw still reasoned 9670 tokens before it replied. The undrafted `low` cell was not drawn and
  the drafted `medium` cell has 7 of 12 draws. The recommendation of `medium` is unchanged.
