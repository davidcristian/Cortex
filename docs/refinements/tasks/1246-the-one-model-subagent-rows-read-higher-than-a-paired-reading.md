# The one-model subagent rows read higher than a paired reading

**Status:** done 2026-11-28
**Area:** inference-model-manager
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

Two readings of 2026-11-18 give one GPU subagent server of gemma-4-E4B at 8K and one slot, with no
drafter, two different sizes on the same build and the same compose settings:

- [subagent budget](../../readings/subagent-budget.md#two-slots-against-two-servers) has 3,328 MiB
  loaded and 3,338 MiB at the peak, 6,387 and 6,407 MiB for two servers, and 3,508 and 3,520 MiB
  for one server of two slots. Each floor was read before the model host started.
- [tier drafters](../../readings/tier-drafters.md#the-default-stack-on-the-card) has 3,068 MiB
  loaded and 3,074 MiB at the peak. Its floor was read after the cortex, which the model host
  starts at boot, had been stopped.

The lower figure agrees with two other rows. The cortex file alone at 16K is 7,553 MiB, and the
cortex beside two servers is 13,686 MiB: 7,553 and twice 3,068 is 13,689. With the higher figure
the cortex would be 7,299 MiB. So the rows of the first reading probably include about 255 MiB
that belongs to the cortex process the host had started at boot and that was still loading.

The subagent request of 3.5 GiB (3,584 MiB) covers one server with its drafter under either
figure, 3,186 MiB at the peak by the second reading and 3,338 MiB with the drafter's 112 MiB by
the first, so no setting depends on which is right. The comment on `DEFAULT_VRAM_GB` in
`brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py` and
`docs/modules/brain-orchestrator-config.md` quote 3338 to 3410 MiB, the first reading and one of
2026-08 on an earlier file, both from before the servers drafted.

What would close it: draw the three shapes of the first reading again, each with its drafter,
with the floor read after the cortex has stopped or with the cortex's own memory read at the same
moment, and replace the rows and the two quotes with what that draw reads.

## History

- 2026-11-18: filed with the drafter settings of the cortex and GPU subagent tiers, whose live
  check read the lower figure
  ([R-1239](1239-no-tier-but-the-deep-one-can-name-a-drafter.md)).
- 2026-11-18: the default stack was read with every context filled
  ([readings](../../readings/tier-drafters.md#the-default-stack-through-tool-turns-a-handoff-and-filled-contexts)):
  one filled request raised a drafting subagent server by 14 MiB, so the request still covers it.
  The rows this task asks for were not drawn.
- 2026-11-27: the two quotes of 3338 to 3410 MiB are still in `config_subagents.py` and the
  module doc. The three shapes are memory rows, not rates, and need the model host on the card;
  they did not fit this slot beside the driver fixes.
- 2026-11-28: done. The three shapes were drawn again with their drafters on build b12375, each
  floor read after the cortex the host starts at boot had stopped: one server of one slot 3,179
  MiB loaded and 3,185 at the peak, two servers 6,358 and 6,370, one server of two slots 3,367
  and 3,377. The floor read 2,648 MiB before the host started, after the cortex stopped and after
  each shape, and one server reads as the tier drafters row to 1 MiB, so the lower figure is the
  right one. The rows replace the first reading's
  ([subagent budget](../../readings/subagent-budget.md#two-slots-against-two-servers)), and
  `config_subagents.py`, the module doc, the subagents compose file and `test_config.py` now give
  3,185 MiB. The 3.5 GiB request stays, by the rule written before the draw: 3,185 MiB and the
  test's 130 MiB margin are under its 3,584 MiB, and a 3.25 GiB request places the same two
  spawns under the default cap.
