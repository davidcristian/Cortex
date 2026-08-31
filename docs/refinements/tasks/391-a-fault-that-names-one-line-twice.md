# A compose-defaults fault that names one line twice says nothing about the note behind it

**Status:** landed 2026-08-23
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-23 by the close of
[R-385](385-a-note-beside-a-compose-value-is-read-as-a-spend.md), which declined to teach the
substitution reader YAML quoting and left the one rough edge that decline is paid for with.

`scripts/composedefaults.py` reads a note written after a value on the same line as a second spend
of the variable it names, deliberately. When that note restates a stale default,
`scripts/defaultcheck.py` reports the group and names the same `path:line` twice among its spends,
measured on a planted note beside the model directory:

    CORTEX_MODELS_DIR: is spelled 5 times and does not carry one default, so the stack takes
    whichever spend it happens to read (docker/docker-compose.gpu.yml:183
    ${CORTEX_MODELS_DIR:-./models}, docker/docker-compose.gpu.yml:183
    ${CORTEX_MODELS_DIR:-./cache}, ...)

Everything in that sentence is true and none of it is the remedy. A reader sees one line twice, has
no reason to suspect a `#`, and the fix, which is to move the note above the value, is written
down in the reader's docstring and nowhere the fault can reach.

**Why it was left.** The decline that opened this was about the reader, and a message is not a
reader: bundling a wording change into the argument for leaving the parse alone would have hidden
one behind the other. Nothing is waiting on it either, no compose file in the tree carrying the
shape.

**What would close it.** A group whose spends share one file and one line is the whole of the
condition, and the fault already has both. Say so where it is built, in
`defaultcheck.disagreement`, and point at the one-line remedy. The care it needs is that the hint
must be true of what was read rather than of what is guessed: one variable really can be spelled
twice on one line with no comment in sight (`"${V:-a}/in:${V:-b}"` is one value spending one
variable twice), so the sentence has to be about the line the two share and not about a `#`
nothing looked for. A branch there needs a test that drives it, and the suite already builds
lines of both shapes.

## Trail

- 2026-08-23: filed by the close of
  [R-385](385-a-note-beside-a-compose-value-is-read-as-a-spend.md), which measured this message
  while proving that the strictness it comes from is reported rather than passing unnoticed, and
  left the wording as the residue of that decline.
- 2026-08-23: landed as `defaultcheck.one_line_hint`, appended to the value disagreement's own
  fault. **This entry's statement of the condition was wrong, and the tree shows it.** It reads "a
  group whose spends share one file and one line is the whole of the condition"; replanting the
  note it quotes makes the gate fail over a group of **five** spends across **four** files, only
  two of which are that line, so a whole-group test would not have fired on the very case the entry was written
  from. The condition shipped is a **repeated** `path:line` within the group, which is what the
  quoted fault actually shows. The care the entry asked for is kept: no `#` is looked for, the
  sentence names the line the two spends share, and the note is offered as the likely reading
  rather than as a finding, so `"${V:-a}/in:${V:-b}"` gets the same hint honestly. Proved on the
  real tree by replanting that note and reading the fault back, then restored and re-run green.
