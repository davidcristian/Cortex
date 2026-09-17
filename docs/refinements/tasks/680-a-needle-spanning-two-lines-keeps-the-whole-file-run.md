# A needle spanning two lines keeps the whole-file run, and it can name the wrong line

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** a sixth registered needle whose rendered template holds a newline, or a replay of one of
the five that do in which the unfound fault names a line the drift is not on. The five are listed by
rendering every mention and keeping those holding `\n`: the two compose files that hold `--threads`
above its substitution, and three needles whose newline only pins them to the start or the end of a
line, in `docs/runbooks/subagents-cpu.md`, `docs/runbooks/llamacpp-gpu.md` and
`brain/Dockerfile.modelhost`.
**Verified:** 2026-09-17

Opened 2026-09-17 by the close of
[R-406](406-the-carried-run-is-measured-over-a-whole-file.md), which moved every needle without a
newline to the per-line reading in `scripts/linereadings.py` and left these five on the opening run
over the whole file that `needles.carried` measures.

That run has the fault R-406 was filed for: an opening satisfied on another line makes it longer
than the drift on the line a reader means, and a drift in the needle's first characters leaves it
stopping wherever else the file spells them. The three needles whose newline sits at one end are one
line with a boundary attached, and the per-line reading could read them with that newline stripped.
The two `--threads` needles really cross a line boundary, and for them the per-line reading would
have to run over each window of two consecutive lines, which adds a loop to `line_runs` and a window
in place of a line number in the clause.

**Why it was left.** All five are presence checks and none has drifted since it was added. The
per-line reading was measured on single-line needles only, and its half floor and tie rule would
need measuring again over windows.

## Trail

- 2026-09-17: opened by the close of
  [R-406](406-the-carried-run-is-measured-over-a-whole-file.md), with the five needles counted by
  rendering the registry at that commit.
