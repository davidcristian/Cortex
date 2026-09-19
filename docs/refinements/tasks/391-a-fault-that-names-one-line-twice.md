# A compose-defaults fault that names one line twice says nothing about the note behind it

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0063](../../adr/ADR-0063-compose-checks.md)

`scripts/composedefaults.py` reads a note written after a value on the same line as a second use
of the variable it names, deliberately. When that note restates a stale default,
`scripts/defaultcheck.py` reports the group and names the same `path:line` twice among the uses
it lists. Measured on a planted note beside the model directory, the fault names
`docker/docker-compose.gpu.yml:183` once for `${CORTEX_MODELS_DIR:-./models}` and again for
`${CORTEX_MODELS_DIR:-./cache}`.

Everything in that message is true and none of it is the remedy. A reader sees one line twice, has
no reason to suspect a `#`, and the fix, which is to move the note above the value, is in the
reader's docstring and nowhere the message reaches.

## History

- 2026-08-23: filed by the close of
  [R-385](385-a-note-beside-a-compose-value-is-read-as-a-spend.md), which measured this message
  while proving that the strictness it comes from is reported rather than silent, and left the
  wording as the residue of that decline.
- 2026-08-23: closed as `defaultcheck.one_line_hint`, added to the value disagreement's own fault
  message. This entry's statement of the condition was wrong. It reads "a group whose spends share
  one file and one line is the whole of the condition"; replanting the note it quotes makes the
  check fail over a group of five uses across four files, only two of which are that line, so a
  whole-group test would not have fired on the very case the entry was written from. The condition
  shipped is a repeated `path:line` within the group, which is what the quoted message actually
  shows. The care the entry asked for is kept: no `#` is looked for, the sentence names the line
  the two uses share, and the note is offered as the likely reading rather than as a finding, so
  `"${V:-a}/in:${V:-b}"` gets the same hint accurately. Proved on the real tree by replanting that
  note and reading the message back, then restoring and re-running green.
