# The prose check reads no string a check prints

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-21

`scripts/prosecheck.py` reads documents, comments and docstrings. It never reads a string literal,
so a sentence a check prints can use a word the table in AGENTS.md bans and nothing fails. That is
how the checks under `scripts/` came to print about 170 such words before
[R-703](703-check-output-uses-banned-words.md) rewrote them.

The survey that task used is the check this one proposes. It walks every non-test `scripts/*.py`
file with `ast`, takes each `str` constant that is not a docstring (the pieces of an f-string
included), passes it through `bannedwords.mask`, and matches it against
`bannedwords.compile_words(bannedwords.read_table(bannedwords.RULES).words)`. On 2026-09-21 it
finds six hits, and none of them is prose:

- `"arm"` in `contrast.py` and `envelopesamples.py`: the key the envelope samples are recorded
  under.
- Two file paths: `cortex_seam/__init__.py` in `wirecouplings.py` and `cortex.seam.v1.rs` in
  `stubcheck.py`, named after the `cortex_seam` package and the proto package, which stay.
- The `--rederive` flag in `volumecheck.py`, which the `image-volumes` recipe passes.
- The label `numbered gate` in `commitlint.py`, which names the words it found in a commit message.

**What would close it.** A reader for string literals, run on `scripts/` at least, whose rule
separates prose from a key, a path, a flag or a quoted word. Three questions to answer first:
whether the brain's printed strings (log messages, exception text) are in scope as well, how a
literal is told apart from prose (a path separator, a leading `--`, a subscript or `.get()`
argument, or a listed exemption like the ones `EXEMPTIONS` already holds), and where the reader
lives, since `prosecheck.py` is at 293 of 300 lines and needs a split by responsibility first.

## History

- 2026-09-21: opened by the close of [R-703](703-check-output-uses-banned-words.md), whose survey
  showed the words come back because no check reads these strings.
