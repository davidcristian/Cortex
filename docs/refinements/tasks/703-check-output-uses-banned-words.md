# The checks print sentences in words the prose table bans

**Status:** done 2026-09-21
**Area:** repo-checks
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)

`prosecheck.py` reads documents, comments and docstrings, and never string literals, so the
sentences the checks themselves print are outside every prose rule. Several use words the table in
AGENTS.md bans, which means an operator reading a failure meets a vocabulary the rules forbid at
the one moment the repo is explaining itself.

Examples: `bindcheck.py` says a bind default `lands unignored` and `lands on` a path;
`composemounts.py` says a short mount `carries an expansion`; `crosscheck.py`'s success line ends
`27 of them pinned to a count`; `wirecouplings.py` describes a value as `quoted across the seam`;
`envelopefloor.py` and its readers print `arm` for a measurement variant, which is also the field
name in the sample files they read.

**What would close it.** Rewrite the printed sentences in plain words, together with the suites
that assert them, and decide separately what to do about the measurement word, which is a key in
the recorded samples as well as a word in the output. A reader's first contact with a check is its
failure line, so this is worth doing; it is filed rather than done because every string here is
asserted by a test, which makes it a code change.

## History

- 2026-09-19: opened after reading the checks' own output against the table.
- 2026-09-21: done. A survey of every non-test `scripts/*.py` string literal against the table
  found 175 banned words in 47 files: 98 in the checks' own summaries, faults and help text, and 69
  in the reasons the registries print after a failure. Every printed sentence is rewritten, with
  the tests asserting it. The measurement variant is called a variant in every sentence, while the
  sample key stays `arm`: the brain's live harnesses write it into recorded samples, so renaming it
  would leave every recorded sample unreadable. Eight hits remain and none is prose: that key, four
  file paths, the `--rederive` flag and a label naming the words `commitlint.py` found.
  `prosecheck.py` reads these strings, under decision 16 of ADR-0040.
