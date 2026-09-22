# A search string spanning two lines keeps the whole-file run and can name the wrong line

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)
**Trigger:** a sixth registered search string whose rendered template contains a newline, or a
replay of one of the five that do in which the unfound fault names a line the mismatch is not on.
The five are listed by rendering every mention and keeping those containing `\n`: the two compose
files that have `--threads` above its substitution, and three whose newline only ties them to the
start or the end of a line, in `docs/runbooks/subagents-cpu.md`, `docs/runbooks/llamacpp-gpu.md` and
`brain/Dockerfile.modelhost`.
**Verified:** 2026-09-17

Every search string without a newline moved to the per-line reading in `scripts/linereadings.py`.
These five stayed on the opening run over the whole file that `searchtexts.longest_prefix`
measures, which has the fault that reading was built to fix: an opening satisfied on another line makes it longer
than the mismatch on the line a reader means, and a mismatch in the first characters leaves it
stopping wherever else the file writes them.

The three whose newline sits at one end are one line with a boundary attached, and the per-line
reading could read them with that newline stripped. The two `--threads` strings really cross a line
boundary, and for them the per-line reading would have to run over each window of two consecutive
lines, which adds a loop to `line_runs` and a window in place of a line number in the message.

**Why it was left.** All five are presence checks and none has changed since it was added. The
per-line reading was measured on single-line search strings only, and its half floor and tie rule
would need measuring again over windows.

## History

- 2026-09-17: opened by the close of
  [R-406](406-the-quoted-run-of-an-unmatched-search-text-covers-a-whole-file.md), with the five counted by rendering
  the registry at that commit.
