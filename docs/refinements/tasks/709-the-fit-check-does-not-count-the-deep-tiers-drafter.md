# The fit check does not count the deep tier's drafter

**Status:** declined 2026-09-22
**Area:** inference-model-manager
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)

A co-resident deployment that names `CORTEX_MODEL_FILE_BRAIN_DRAFT` and leaves
`CORTEX_SWAP_BRAIN_VRAM_MIB` at the plain tier's figure passes the fit check wherever that figure
fits, and starts a load about 1000 MiB larger than it declared. On 2026-09-22 that load, beside the
E4B tier and 917 to 941 MiB short by the free figure, decoded at 0.79 to 0.80 of the drafting tier's
solo rate. The spill watch is not the check for it: the fastest completion of a handoff decides, a
floor has to sit under the slowest healthy completion (a tool call or answer text for a drafting
tier), and the overcommitted reasoning trace's best was 1.02 of the slowest healthy drafting tool
call. A floor taken on the plain tier misses both turns. The readings are in
[co-residency](../../readings/co-residency.md).

**The fix, which does not rest on decode.** The fit check counts the drafter instead of asking the
operator to. The model host already resolves the drafter's path, so `GET /health` could report,
for each roster tier, the size on disk of the files its argv loads beside the model, and the swap
in would compare the free figure against `CORTEX_SWAP_BRAIN_VRAM_MIB` plus the deep tier's figure,
the runbook's drafter step then leaving the setting at the plain tier's cost. On the 2026-09-22
card that check refuses the load: 18876 MiB of `memory.free` against 19125 plus the drafter's 911
MiB file.
What the lander settles first:

- the file is 911 MiB and costs 997 to 1020 MiB on the card, so a check from file size alone
  counts about a tenth of the drafter too little;
- [ADR-0004](../../adr/ADR-0004-model-lineup.md) keeps the drafter out of the `ModelHost` port by
  design, so the field names files a tier loads rather than a drafter, and ADR-0055 decision 2
  changes with it;
- the placer's charge for the window, ADR-0055 decision 3, uses the same declared figure.

Refusing co-residency at startup whenever the deep tier drafts is the alternative, and it forbids a
card large enough for all three.

## History

- 2026-09-22: opened by the close of
  [R-698](698-a-drafter-sized-spill-is-unmeasured-against-the-decode-floor.md), whose run showed
  the spill watch misses this overcommit on a reasoning trace.
- 2026-09-22: declined. The drafting overcommit it measured is refused by the check as shipped,
  since 18876 MiB of `memory.free` is short of the plain 19125 and of the runbook's 20125, so the
  gap is a card whose free memory falls within about 1000 MiB above the figure. The drafter is one
  of four settings that move the deep tier's cost with the figure unchanged, beside the model
  file, context size and layer count, and none reaches the brain container. Counting its file sees
  that one, counts 911 of its 997 to 1020 MiB, and turns the declared figure into a partial one; a
  startup refusal needs the same port change and refuses a card with room for all three.
  [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md) decision 2 now says the figure
  describes the tier's whole command line and is declared again when any of it changes, and its
  rejected alternatives name both designs.
