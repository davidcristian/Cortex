# A new model host container compiles the card's kernels again

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-22

The card's library compiles the engine's kernels on their first use and keeps them under
`/home/cortex/.nv/ComputeCache/`, in the model host container's writable layer. A new
container starts without them, so the first deep load after every stack start pays the compile
in its first request. On 2026-11-22, on the deep pick's Q4 file at compose defaults, that first
prompt pass over 896 tokens read 4.94 times a later pass, where a later load in the same
container read 1.38 ([readings](../../readings/deep-first-request.md)). With a host directory
bound at `/home/cortex/.nv`, the first deep load of three new containers read 1.37 and the load
did not grow, so the time is removed and not moved into the load. The client's first token on
those loads came at 0.28 of an untreated first load's.

**Proposed, not built: a named volume for that directory** on the `model-host` service of
`docker/docker-compose.gpu.yml`, mounted at `/home/cortex/.nv`. It was not built on these rows
because no rule for the change was written before they were drawn. The rule is below, and a
build draws its rows against untreated rows of the same night.

**The rule a build must pass**, on the Q4 file at compose defaults, three new containers a
cell:

1. **The first token.** With the volume already written by an earlier container, the first
   deep load of a new container has a first prompt pass over 896 tokens of 1.6 later passes or
   less (untreated 4.94, the bound rows 1.33 to 1.38). The client's first token on it comes at 0.40 or
   less of the untreated first load's.
2. **The whole deep turn**, the load, the first token and 1,000 tokens written, reads under 1
   of the untreated first load's turn by the medians. The first token is 0.05 of that turn and
   the load 0.77, so the load must not grow by what the first token saves.
3. **What must not change.** The load is within 0.10 of the untreated loads, and
   `CORTEX_SWAP_LOAD_TIMEOUT_S` and `CORTEX_INFERENCE_STALL_TIMEOUT_S` keep their values. The
   tier's highest reading above the floor is within 16 MiB of the untreated rows' (16,991 to
   17,003 MiB here). The first request's write rate is within 0.05 of the untreated one.
4. **An empty volume** reads as today: the first container's first load is within 0.10 of an
   untreated first load, and the volume holds the files afterwards (51 MB here, after the
   cortex tier's load and the deep tier's two requests).
5. **A volume another image wrote.** One launch of a different engine build on the same volume
   starts and answers, and its first load reads no longer than an untreated first load. The
   library names each cached file by a hash, and no row here read a directory another build
   wrote.
6. `volumecheck.py` and `bindcheck.py` pass, and the teardown in the runbook removes the
   volume with the others.

Not part of this proposal: the smaller fixed time every new server process pays, 0.39 of a later
pass. A one-token request before use moves it into the load and adds to it, so nothing is
proposed for it.

## History

- 2026-11-22: filed by the rows of both Qwen files' first request after a load, which
  [R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md)
  compares the two files on. Rows on the Q4 file the same date named the time and what removes
  it. The NVFP4 file's later loads are
  [R-1293](1293-the-nvfp4-files-first-request-is-drawn-only-on-a-new-containers-first-load.md).
