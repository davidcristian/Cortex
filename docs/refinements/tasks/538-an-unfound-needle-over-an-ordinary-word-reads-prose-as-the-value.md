# An unfound needle whose value is an ordinary word reads prose as the value still spelled

**Status:** landed 2026-09-04
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-02 by the close of
[534](534-the-declared-kind-word-has-no-site-to-hold-it.md), whose first mutation showed it.

`needles.unfound` gives an unfound needle two readings: how much of the needle the file carries
and where that run stops, and whether the file still spells the value as a token of its own, with
the line it is nearest on. The second reading exists to say that what moved is shape rather than
value, which points the reader at a neighbouring constant (ADR-0023 bind-host addendum). It counts
every bounded occurrence of the rendered value in the file, and for a value that is an ordinary
word the file's own prose supplies them. With the enum value renamed alone, the gate reported that
`provenance.py` still spells `sender` as a token of its own in seven places, the nearest on a
docstring line reading "by sender must not sweep a URI", and concluded that what moved was likely
shape and the constant to change might not be the one named. What moved was the value, and the
first reading, stopping at `SENDER = "` on the member's own line, said so.

**Why it was left.** The verdict is right and the first reading is right; only the hedge is wrong,
and it is wrong for a value the file uses as a word. This mutation is the first time a run here
showed the hedge misreading prose. Narrowing the second reading, say to occurrences inside quotes
or on a line that also carries part of the needle, is a design question about what counts as a
spelling of a value, and one entry is not enough to settle it on.

**What would close it.** Decide what a spelling of the value looks like when the value is a word,
and change `unfound` so the hedge is stated only when one is found; or state both readings without
concluding which moved, and leave the conclusion to the reader. Either way the suite's cases for
`unfound` gain one over a value the file also uses in prose.

## Trail

- 2026-09-02: opened by the close of
  [534](534-the-declared-kind-word-has-no-site-to-hold-it.md), recorded in its ADR-0029
  declared-kind-word addendum.
- 2026-09-02: a second instance, in the close of
  [537](537-the-declaration-field-names-are-bare-literals-on-both-sides.md). With the value
  field's two bindings re-spelled `from` and both contracts left alone, the hedge found `from`
  thirteen times in the tools contract's prose and concluded that what moved was likely shape,
  when the value had (ADR-0029 declaration-fields addendum).
- 2026-09-04: landed. The trigger had fired: the two field entries hold the values `kind` and
  `value`, and every value-rendering mention of them sits over a module contract whose prose
  spells the same word away from the needle. Across the whole registry, 65 of 288 mentions render
  a value made of letters and underscores into a file that spells it away from the needle, 31 of
  them a single word. `needles.verdict` now states the strong form only where the value's line is
  the line the run stops on, and reports both readings without naming a mover otherwise; both
  recorded misreadings were replayed in a copy of the tree before and after (ADR-0029
  word-valued-verdict addendum).
