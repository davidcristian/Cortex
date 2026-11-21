# The deep tier cannot set a template's reasoning effort or preserve flag

**Status:** done 2026-11-21
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

The Qwen3.8 template reads `reasoning_effort` (`xhigh` by default, `high` rendered as `xhigh`,
`medium`, `low`; any other value raises with thinking on) and `preserve_thinking` (on by default).
With no effort sent, the deep pick, Qwen3.8-27B (ADR-0004 decision 8), runs at `xhigh`, which is
not its best measured setting. The deep tier sends the level `CORTEX_REASONING_EFFORT_BRAIN`
names, `medium` by default, and never the preserve flag. At the deep tier's earlier
8192 context that stopped on 10 of 12 draws against 12 of 12 at `medium` and `low`, the misses
filling the context with reasoning ([deep candidates](../../readings/deep-candidates.md)). At
the shipped 16384 it stopped on 11 of 12 without a drafter and 12 of 12 with its draft layer, at
a median of 2327 and 2883.5 reasoning tokens a draw, and at `medium` on 12 of 12 at a median of
1182.5 ([the stop rows at 16384](../../readings/deep-candidates.md#the-stop-rows-at-16384)).

Only the Qwen3.8 template reads the effort: the gemma, Qwen3.5 and Qwen3.6 templates render every
value the same as none ([thinking-switch readings](../../readings/thinking-switch.md#the-effort-and-preserve-settings)).
On them depth is set only by the thinking switch and the trace budget.

## Proposal

**Step one, a default level for the deep tier.** Built on 2026-11-21, with `medium` as the default
([ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md) decisions 17 to 20).
`GenerationBounds.effort` is an optional `ReasoningEffort` of three, and the brain setting
`CORTEX_REASONING_EFFORT_BRAIN` (`low`, `medium` or `high`, a typo failing the start) puts it on
the deep reply's bounds alone. The adapter reads the leased server's `chat_template_caps` from
`GET /props` on every such request and sends `reasoning_effort` under a name that server lists,
so the top level reaches Qwen3.8 as `xhigh`. A template that reads no effort gets the request
without the field, and the brain logs that once for the endpoint. Nothing is held by a model
server, so a swap changes nothing. The model host's `--reasoning-effort` flag is rejected: it
passes any value unchecked and a bad one fails every reply while the tier reports ready. The
preserve flag stays out until a multi-turn row shows the empty earlier thoughts matter; then the
argv takes `--no-reasoning-preserve` ([R-1276](1276-the-deep-tier-never-sends-the-templates-preserve-flag.md)).

**The rule that decides the default**, written on 2026-11-21 before any row it names was drawn.
The setting's default becomes `medium` when all three hold on Qwen3.8-27B as the model host starts
it with its draft layer (16384, one slot, `q8_0`), and stays unset when one does not:

1. **A handoff renders the level.** With the setting at `medium`, a handoff through the brain
   passes every item of [a handoff on the deep pick](../../readings/model-swap.md#a-handoff-on-the-deep-pick),
   the brain logs `reasoning effort sent` with `sent_as` `medium`, and the deep request's prompt
   is 38 tokens shorter than the same request with the setting unset. That is the `xhigh`
   sentence the template leaves out at `medium`: 322 against 284 prompt tokens on build b12375.
2. **The injection text rows do not read apart.** 100 framed and 100 unframed draws, drawn as
   the draft layer rows of 2026-11-21 were
   ([injection text rows](../../readings/injection-text-rows.md)) with `reasoning_effort` `medium`
   in the request, the field the brain sends. Against the `xhigh` row's 0 framed obeyed of 100,
   5 or fewer does not read apart and 6 or more does (Fisher exact, two-sided: p 0.059 at 5 and
   0.029 at 6). A void draw counts as obeyed.
3. **`medium` stops as often and reasons less.** The drafted `medium` cell is completed to 12
   draws by its 5 undrawn ones (Q3 d2 and d3, Q4 d1 to d3). Over the 24 draws of the two `medium`
   cells, at least 23 stop, which is the count over the 24 `xhigh` draws, and the drafted
   `medium` cell's median reasoning is under the drafted `xhigh` cell's 2883.5 tokens. The 19
   drawn so far all stopped, so the condition fails at two misses in the 5.

Condition 3 counts both cells because one cell cannot show a loss: against 12 of 12, a cell of 12
reads apart only at 7 or fewer, and the drafter left the `xhigh` stop count where it was predicted,
so the two cells of a level are one sample of 24. A rule of 12 of 12 on the drafted cell alone
would turn on a single Q4 draw. The median is in the condition because shorter reasoning is the
only reason to change the default. A failed condition is recorded with its rows and changes
nothing that ships. When the default is set, a deep tier on a gemma file logs the warning for a
level nobody set, so the same change lowers that line to `INFO` for the default's own level.

**Step two, optional: one user preference**, is
[R-1275](1275-no-user-preference-sets-the-reasoning-effort.md).

**What closes it.** The three rows of the rule drawn and the default decided by it. Declined if ADR-0004 drops both Qwen3.8 candidates
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
- 2026-11-21: step one built with the default unset: `GenerationBounds.effort`, the adapter's
  `/props` check and `CORTEX_REASONING_EFFORT_BRAIN`. Checked against b12375 first: `/props`
  lists `low`, `medium` and `xhigh` and no `high`, so the adapter sends a name the server lists
  where the proposal sent `high`, and a failed or negative check is logged once for an endpoint,
  not on every request. The rule that decides the default is in the proposal, written before its
  rows.
- 2026-11-21: the setting read live, after the rule was in the tree. Two handoffs through the
  brain on the pick with its draft layer: at `medium` the brain asked the deep server's `/props`
  once and logged `reasoning effort sent`, and the deep request had 861 prompt tokens against 899
  with the setting unset, where the brain asked nothing and logged nothing. Both runs passed
  every item of the handoff reading
  ([readings](../../readings/model-swap.md#a-handoff-on-the-deep-pick)), so condition 1 of the
  rule holds. Conditions 2 and 3 are not drawn.
- 2026-11-21: filed
  [R-1274](1274-the-effort-checks-props-read-has-no-measured-answer-time.md): the `/props` read
  the adapter makes before each deep completion has no measured answer time.
- 2026-11-21: done. The rule's two undrawn conditions were drawn on the pick with its draft layer
  ([readings](../../readings/deep-effort.md)). Condition 2: 0 of 100 framed and 0 of 100
  unframed injection draws obeyed at `medium`, none void, as at `xhigh`. Condition 3: the drafted
  `medium` cell's 5 undrawn draws all stopped, so 24 of the 24 `medium` draws stopped against 23
  of 24 at `xhigh`, and the drafted cell's median of 2378 reasoning tokens is under 2883.5. All
  three conditions hold, so `CORTEX_REASONING_EFFORT_BRAIN` defaults to `medium`, an empty value
  names no level, and the line for a template that reads none is logged at `INFO` for the default
  and at `WARNING` for a level the deployment wrote (ADR-0049 decisions 19 and 20). The drafted cell's median is above the 1000 to 1900 the stop rows
  predicted for it. Filed: [R-1275](1275-no-user-preference-sets-the-reasoning-effort.md), the user preference that was step two, and
  [R-1276](1276-the-deep-tier-never-sends-the-templates-preserve-flag.md), the preserve flag.
- 2026-11-21: the default read live in two handoffs on compose defaults. With the variable absent
  the brain read the deep server's `/props` once and logged `reasoning effort sent` with `sent_as`
  `medium`, and the deep request had 861 prompt tokens. With it empty the brain logged no line
  about an effort and read no `/props`, and the request had 899. Both passed every item of the
  handoff reading ([readings](../../readings/model-swap.md#a-handoff-on-the-deep-pick)).
