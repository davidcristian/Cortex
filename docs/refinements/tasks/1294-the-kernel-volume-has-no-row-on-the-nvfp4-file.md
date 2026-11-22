# The kernel volume has no row on the NVFP4 file

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-22

The model host keeps the kernels the card's library compiles in the `compute-cache` volume
(`docker/docker-compose.gpu.yml`), so a new container's first deep request does not compile
them again. The rows that decided it were drawn on the deep pick's Q4 file alone: there the
first token of a new container's first deep load comes at 0.286 of an untreated one's
([readings](../../readings/deep-first-request.md#a-volume-for-the-compiled-kernels)).

The NVFP4 file compiles kernels of its own, and its first load's fixed time is 2.03 times the
Q4 file's ([readings](../../readings/nvfp4-deep-pair.md#the-deep-turn-of-a-handoff)). In a
container that stayed up its later loads had 0.07 of that time, so the volume should take the
same share from a new container's first load. No row drew it.
[R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md) compares
the two files on the first handoff after a stack start, and with the volume a stack pays that
handoff once a volume and engine build, not once a start.

**To draw**, on one night with untreated first loads of the same file beside them: three new
containers on a volume an earlier container of the NVFP4 file wrote, and one on a volume that
holds only the Q4 file's kernels, which is what a deployment has when it changes file.
`nvfp4-probes/k2vol.py` under `measurements/model-baseline-2026-11-16/` draws these launches
for the Q4 file.

## History

- 2026-11-22: filed when the volume was added on rows of the Q4 file.
