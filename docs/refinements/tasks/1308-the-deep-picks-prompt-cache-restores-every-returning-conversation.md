# The deep pick's prompt cache restores every returning conversation

**Status:** declined 2026-11-26
**Area:** inference-model-manager
**Origin:** [ADR-0059](../../adr/ADR-0059-prompt-cache-per-tier.md)

The deep tier runs `--cache-ram 0` (`_NO_PROMPT_CACHE` in
`brain/packages/model_manager/src/cortex_model_manager/config.py`) because on gemma-4-31B a cached
conversation cost about 3.5 GiB, the default 8192 MiB ceiling held two, and no returning request
was restored. On the deep pick, `Qwen3.8-27B-UD-Q4_K_M` at the deep tier's argv, a cached
conversation of 6184 prompt tokens cost 951 and 959 MiB, and with the cache at 8192 MiB all nine
returns of three rotating conversations were restored: 20 prompt tokens evaluated each, against
6183 or 6184 with the cache off. The cgroup's peak was 19302 MiB of the 24 GiB cap, against 17043
off ([prompt cache](../../readings/prompt-cache.md#the-deep-pick)).

So the cost reason does not hold for the pick. Whether a cache would pay is a question about the
traffic: the rotating shape is the one the cache serves, and a handoff loads the deep tier for one
turn, which may never return to a conversation whose slot another request took. The argv stays at
zero, since no rule written before the row called for a change.

What would close it: count, over the deep tier's requests in real handoffs (one turn with tool
calls, and the stop and resume paths), how many start from a prompt the slot does not already
hold, with that rule written first. If none does, restate decision 4 on that ground and close as
declined; if some do, size `--cache-ram` for the deep tier by the per-conversation cost above,
check the peak against the model host's cap beside the cortex's 8192 MiB, and measure what the
returning requests save.

## History

- 2026-11-23: filed by the prompt cache row of
  [R-741](741-a-qwen38-27b-deep-tier-has-no-measured-fit-figure-or-decode-floor.md), drawn on
  build b12375. `--cache-ram 0` is unchanged.
- 2026-11-24: counted off the model host logs of nine recorded handoffs to the pick on build
  b12375: twelve deep requests, nine the first of their server, three the second with the slot
  holding the first, none a possible return
  ([counts](../../readings/prompt-cache.md#deep-requests-in-handoffs)). No deep turn in
  them called a tool and none took the stop or resume path, so by the rule written before the
  count the task stays open until a live handoff draws those two.
- 2026-11-26: declined. Four live handoffs to the pick on build b12375, on compose defaults with
  memory and escalation on: one whose deep model called `forget_memories`, one stopped 20 s into
  the deep phase, the same request asked for again, and one asking for tools the defaults leave
  off. Nine deep requests: four first, four new, one held, no possible return
  ([counts](../../readings/prompt-cache.md#deep-requests-in-handoffs)). A stop ends the server,
  so the request asked for again started on an empty slot. By the rule written before the draw,
  ADR-0059 decision 4 is restated on that ground and `--cache-ram 0` stays. The draw also showed
  a forget request worded as a use of the tool being refused, recorded
  [with the forms left unread](../../readings/forget-freeze.md#forms-left-unread-at-the-freeze-2026-11-26).
