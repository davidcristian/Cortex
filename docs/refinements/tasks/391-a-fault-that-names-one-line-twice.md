# A compose-defaults fault that names one line twice says nothing about the note behind it

**Status:** open, actionable
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
  while proving the strictness it comes from is loud rather than silent, and left the wording as
  the residue of that decline.
