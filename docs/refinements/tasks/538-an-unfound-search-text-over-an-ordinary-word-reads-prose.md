# An unfound search text whose value is an ordinary word reads prose as the value

**Status:** done 2026-09-04
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`searchtexts.unfound` reports two things about a search text its target file no longer contains: how
much of the text the file still has and where that run stops, and whether the file still contains
the value as a word of its own, with the nearest line. The second report exists to say that what
changed is the form rather than the value, which points the reader at a neighbouring constant
(ADR-0042 decision 25). It counts every bounded occurrence of the value in the file, and for a value
that is an ordinary word the file's own prose supplies them. With the enum value renamed alone, the
check reported that `provenance.py` still contains `sender` as a word in seven places, the nearest
on a docstring line, and concluded that the form had probably changed and the named constant might
be the wrong one. The value had changed, and the first report, stopping at `SENDER = "` on the
member's own line, said so.

## History

- 2026-09-02: opened by the close of [534](534-the-declared-kind-word-has-no-site-to-hold-it.md),
  recorded in ADR-0042.
- 2026-09-02: a second case, in the close of
  [537](537-the-declaration-field-names-are-bare-literals-on-both-sides.md). With the value field's
  two bindings renamed to `from` and both module contracts left alone, the report found `from`
  thirteen times in the tools contract's prose and again concluded that the form had probably
  changed, when the value had (ADR-0042).
- 2026-09-04: done. Across the whole registry, 65 of 288 mentions write a value made of letters and
  underscores into a file that also contains that word away from the search text, 31 of them a
  single word. `searchtexts.verdict` now states the strong form only where the value's line is the
  line the match run stops on, and otherwise reports both readings without saying which changed;
  both recorded misreadings were replayed in a copy of the tree before and after (ADR-0042).
