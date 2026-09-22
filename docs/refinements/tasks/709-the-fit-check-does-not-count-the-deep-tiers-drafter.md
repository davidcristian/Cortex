# The fit check does not count the deep tier's drafter

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)
**Verified:** 2026-09-22

A co-resident deployment that names `CORTEX_MODEL_FILE_BRAIN_DRAFT` and leaves
`CORTEX_SWAP_BRAIN_VRAM_MIB` at the plain tier's 19125 MiB passes the fit check and starts a load
about 1000 MiB larger than it declared. On 2026-09-22 that load, beside the E4B tier and 917 to 941
MiB short by the free figure, decoded at 0.79 to 0.80 of the drafting tier's solo rate. The spill
watch is not the check for it: the fastest completion of a handoff decides, a floor has to sit
under the slowest healthy completion (a tool call or answer text for a drafting tier), and the
overcommitted reasoning trace's best was 1.02 of the slowest healthy drafting tool call. A floor
taken on the plain tier misses both turns. The readings are in
[co-residency](../../readings/co-residency.md).

**The fix, which does not rest on decode.** The fit check counts the drafter instead of asking the
operator to. The model host already resolves the drafter's path, so `GET /health` could report,
for each roster tier, the size on disk of the files its argv loads beside the model, and the swap
in would compare the free figure against `CORTEX_SWAP_BRAIN_VRAM_MIB` plus the deep tier's figure,
the runbook's drafter step then leaving the setting at the plain tier's cost. On the 2026-09-22
card that check refuses the load: 19201 MiB free against 19125 plus the drafter's 911 MiB file.
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
