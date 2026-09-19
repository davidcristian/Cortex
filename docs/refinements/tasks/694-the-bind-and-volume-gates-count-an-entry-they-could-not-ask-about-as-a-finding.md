# The bind and volume gates count an entry they could not ask about as a finding

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-19

Opened 2026-09-19 by the change that made `scripts/bindcheck.py` and `scripts/volumecheck.py`
count a compose file their reader refused as a file, with a summary of its own, recorded in the
[ADR-0026 addendum on quoting a nested spend
whole](../../adr/ADR-0026-prose-style-gates.md).
That change separated the refused files only. One level down, each gate still counts an entry it
read but could not ask its question about under the summary for the findings its rule exists to
report. Measured on 2026-09-19 over one scratch compose file whose service spells
`image: ${IMG}` and a bind source `./models/${TIER}`:

- `bindcheck.py --root <scratch>` printed `docker-compose.yml:5: cannot reduce source
  './models/${TIER}' to a path` and ended with `1 compose bind default(s) land unignored in the
  tree`, with the remedy of pointing the default outside the repo or ignoring it. The source was
  never reduced, so no landing was found at all. A git that answered neither yes nor no about a
  landing (`BindCheckError` from `is_tracked` or `is_ignored`) is counted the same way.
- `volumecheck.py --root <scratch>` counted the substituted image as one of `11 image volume
  declaration(s) go uncovered or unrecorded` (the other ten were the record's rows, stale on a
  tree that names none of them), with the remedy of mounting the path or running
  `just image-volumes`, which does nothing for a substitution. A build-only service with no
  project name to key it under (`_UNPROJECTED`) is counted the same way. In both cases the gate
  never learned which image the service runs, so no declaration was compared.

Each fault's own detail already names the right remedy, so what is wrong is the count and the
remedy in the summary line.

**The fix.** In `bindcheck.py`, keep the mounts `_spots` raised `BindCheckError` on apart from the
unignored landings where `check_file` catches it, and give them a summary of their own (a mount
count, and the remedy of writing the source as a path or a defaulted variable, or of the git
failure the fault names). In `volumecheck.py`, keep the `_SUBSTITUTED` and `_UNPROJECTED` faults
apart from the declaration findings in `check_file`, with a summary saying the image a service
runs could not be named. `volumecheck.py` is at 297 of 300 lines, so this needs a split by
responsibility first; the five fault templates at its top are one candidate. Assert each summary
whole, as the tests of the refused-file summary do.

## Trail

- 2026-09-19: opened by the change that counted a refused compose file as a file in the bind and
  volume gates, whose [ADR-0026
  addendum](../../adr/ADR-0026-prose-style-gates.md)
  records the run that showed it.
