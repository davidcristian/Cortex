# The bind and volume gates count a file they could not read as a finding

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-19

Opened 2026-09-19 by the change that split `scripts/defaultcheck.py`'s failing summary into one
sentence per kind of fault, recorded in the [ADR-0026 addendum on quoting a nested spend
whole](../../adr/ADR-0026-prose-style-gates.md).

`defaultcheck.py` counted a compose file its reader refused as a variable that does not carry one
default, and now prints refused files and disagreeing variables as two summaries. The two gates
that walk the same files through `composefiles.py` count a refused file the same way. Measured on
2026-09-19 over one scratch compose file that is not UTF-8 (`image: \xff\xfe`):

- `bindcheck.py --root <scratch>` printed `docker-compose.yml:0: 'utf-8' codec can't decode ...`
  and ended with `1 compose bind default(s) land unignored in the tree`, with the remedy of
  pointing the default outside the repo or ignoring it. The file declares no bind at all.
- `volumecheck.py --root <scratch>` counted the file as one of `11 image volume declaration(s) go
  uncovered or unrecorded`; the other ten were stale record rows, since the scratch tree names no
  image.

Neither is the two-kind shape `defaultcheck.py` had, which is why they were not split in the same
change. `bindcheck.py` has three kinds: a file `check_file` could not read (line 0), a mount whose
source could not be reduced or about which git could not answer (`BindCheckError`, on the mount's
line), and a landing git neither tracks nor ignores, which is the only one its summary describes.
`volumecheck.py` has six, each already carrying its own remedy in its detail: a refused file, a
service with no project to name its built image by (`_UNPROJECTED`), an image spelled through a
substitution (`_SUBSTITUTED`), an unrecorded image, an uncovered declared path, and a stale record
row, plus what `dockerfilevolumes.undeclared` reports for a build; its summary names two of them.

**The fix.** For each gate, keep the refused files apart from the findings where `check_file`
(`bindcheck.py`) or `read_file` (`volumecheck.py`) makes them, and print a refused-file summary of
the shape `defaultcheck.py` prints, `{n} compose file(s) could not be read, so ...`, before the
existing one, which then counts findings only. In `bindcheck.py`, decide whether an unanswered
mount is a third summary or a named part of the landing one; in `volumecheck.py`, decide whether
the existing sentence should name every kind it counts. Assert each summary whole in the gate's
test file, including a run carrying a refused file beside a finding, and mind `volumecheck.py`'s
line count (284 of 300 on 2026-09-19).

## Trail

- 2026-09-19: opened by the change that split `defaultcheck.py`'s summary, whose [ADR-0026
  addendum](../../adr/ADR-0026-prose-style-gates.md)
  records the run that showed it.
