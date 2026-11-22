# No scan fails when the kernel volume's mount is removed

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0067](../../adr/ADR-0067-image-volume-record.md)
**Verified:** 2026-11-22

`docker/docker-compose.gpu.yml` keeps the kernels the card's library compiles with two lines of
the `model-host` service: the `compute-cache` volume mounted at `/var/tmp`, and
`CUDA_CACHE_PATH=/var/tmp/ComputeCache` in its environment. The variable must name a directory
under the mount, and nothing compares the two. With either line removed, or with the variable
naming a directory outside the mount, the kernels are written outside the volume, and every
new container compiles them again in its first deep request. The stack starts and answers the
same, and no log line names the directory
([readings](../../readings/deep-first-request.md#a-volume-for-the-compiled-kernels)).

`volumecheck.py` and `bindcheck.py` both read the mount: the first fails when its `target:`
line is removed, the second when it is rewritten as a bind of a directory in the repo. Both
pass with the whole mount removed, since the image declares no `VOLUME` there, and with the
variable removed. `settingscheck.py` passes without the variable too: it reads the settings
the model manager's classes declare, and the library reads this one, not a class.

Two ways to check it, neither built:

- A scan of the compose file alone: a service that sets `CUDA_CACHE_PATH` mounts a named
  volume at that directory or above it, and a service that mounts `compute-cache` sets the
  variable. It reads no image and needs no rebuild.
- Declare `VOLUME /var/tmp` in `brain/Dockerfile.modelhost`. `volumecheck.py` then fails a
  service that runs the image and mounts nothing there. It needs the image rebuilt and
  `just image-volumes` to record the row, a container of the image started outside compose
  then takes an anonymous volume there, and it does not read the variable.

## History

- 2026-11-22: filed when the volume was added. The image was not rebuilt on that date, so the
  second way could not be recorded.
