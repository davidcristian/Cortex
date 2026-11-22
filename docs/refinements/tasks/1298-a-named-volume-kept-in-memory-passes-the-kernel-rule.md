# A named volume kept in memory passes the kernel rule

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0067](../../adr/ADR-0067-image-volume-record.md)
**Verified:** 2026-11-22

`scripts/kernelcache.py` accepts a mount over the `CUDA_CACHE_PATH` directory when the entry
under the service is a named volume or a bind. It does not read the top-level `volumes:` block,
where a named volume can be given `driver_opts` with `type: tmpfs`. Docker keeps such a volume
in memory and empties it when its last container stops, so every new container compiles the
card's kernels again, which is the loss the rule reports. On 2026-11-22 the `compute-cache`
volume in `docker/docker-compose.gpu.yml` was given `driver: local` and `driver_opts` of
`type: tmpfs` and `device: tmpfs`, and `volumecheck.py --root ..` exited 0.

A rule that fails safe reads each top-level volume declaration and accepts only one with no
`driver`, `driver_opts` or `external` key, so that every form the scan does not read fails.
`composeservices.py` skips every top-level block except `services:` today, so the rule needs a
reader for that block. A bind whose host directory is itself in memory cannot be read from a
compose file and stays outside the scan.

## History

- 2026-11-22: filed when the kernel rule began to refuse a tmpfs mount.
