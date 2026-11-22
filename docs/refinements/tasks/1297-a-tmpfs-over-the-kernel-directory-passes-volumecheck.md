# A tmpfs over the kernel directory passes volumecheck

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0067](../../adr/ADR-0067-image-volume-record.md)
**Verified:** 2026-11-22

`scripts/kernelcache.py` fails a service whose `CUDA_CACHE_PATH` is under no mount of that
service. It takes the mounts from `Service.covered` in `composeservices.py`, which lists every
target under `volumes:` and `tmpfs:` without the mount's type. A tmpfs at the directory
therefore passes. A tmpfs is emptied with its container, so every new container compiles the
card's kernels again, which is the loss the rule reports. On 2026-11-22 the model host's mount
in `docker/docker-compose.gpu.yml` was rewritten as `type: tmpfs` with `target: /var/tmp`, and
`volumecheck.py --root ..` exited 0.

The fix keeps the type beside each target. `composetargets.py` has an entry's `type` when it
closes a long entry, and the source of a short one, so `Service` can list the targets of named
volumes and binds apart from the tmpfs ones, and `kernelcache.py` compares the directory with
those only. The first rule of `volumecheck.py` keeps reading `covered`, where a tmpfs is a
correct cover.

## History

- 2026-11-22: filed when the kernel rule was added to `volumecheck.py`.
