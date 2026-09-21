# The bind and volume checks count an entry they could not ask about as a finding

**Status:** done 2026-09-21
**Area:** repo-checks
**Origin:** [ADR-0063](../../adr/ADR-0063-compose-checks.md)

`scripts/bindcheck.py` and `scripts/volumecheck.py` now count a compose file their reader refused
separately, with a summary of its own. One level down, each still counts an entry it read but could
not ask its question about under the summary for the findings its rule exists to report. Measured on
2026-09-19 over one scratch compose file whose service has `image: ${IMG}` and a bind source
`./models/${TIER}`:

- `bindcheck.py --root <scratch>` printed `docker-compose.yml:5: cannot reduce source
  './models/${TIER}' to a path` and ended with `1 compose bind default(s) land unignored in the
  tree`, advising the author to point the default outside the repo or ignore it. The source was
  never reduced, so no such directory was found at all. A git that answered neither yes nor no
  (`BindCheckError` from `is_tracked` or `is_ignored`) is counted the same way.
- `volumecheck.py --root <scratch>` counted the substituted image as one of `11 image volume
  declaration(s) go uncovered or unrecorded` (the other ten were the record's rows, stale on a tree
  that names none of them), advising the author to mount the path or run `just image-volumes`, which
  does nothing for a substitution. A build-only service with no project name to key it under
  (`_UNPROJECTED`) is counted the same way. In both cases the check never learned which image the
  service runs, so no declaration was compared.

Each message's own detail already gives the right advice, so what is wrong is the count and the
advice in the summary line.

**The fix.** In `bindcheck.py`, keep the mounts `_spots` raised `BindCheckError` on separate from
the unignored directories where `check_file` catches it, and give them a summary of their own (a
mount count, and advice to write the source as a path or a defaulted variable, or the git failure
the message names). In `volumecheck.py`, keep the `_SUBSTITUTED` and `_UNPROJECTED` messages
separate from the declaration findings in `check_file`, with a summary saying the image a service
runs could not be named. `volumecheck.py` is at 297 of 300 lines, so this needs a split by
responsibility first; the five message templates at its top are one candidate. Assert each summary
whole, as the tests of the refused-file summary do.

## History

- 2026-09-19: opened by the change that counted a refused compose file separately in the bind and
  volume checks, recorded in [ADR-0063](../../adr/ADR-0063-compose-checks.md) decision 1.
- 2026-09-21: done. Re-measured first: the reader now refuses a short mount with a substitution, so
  the scratch file needed a long-form bind to show the miscount, which it did as described. Both
  checks now keep an entry they could not ask about in `Scan.unasked`, with a summary of its own. In
  `volumecheck.py` that also covers the Dockerfile side the entry did not name: a build path
  written through a substitution, a build reaching no Dockerfile, a Dockerfile the reader refuses,
  and a recorded trigger it refuses. The file was at 228 lines, so no split was needed.
