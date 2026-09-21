# The reading that says a file still contains a value does not say where

**Status:** done 2026-08-25
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

When a rendered search text is not found, `searchtexts.unfound` adds the reading that decides who
the fault is about: whether the file still contains this constant's own value as a token of its own,
which is the evidence that what moved is the surrounding shape and the entry named is not the entry
to change. It searches the bare value across the whole file and reports a yes or a no. It never
says which line the yes came from.

Measured live while [R-398](398-a-rendered-integer-is-a-token-inside-a-decimal.md) was being
closed, by retuning `DEFAULT_STOP_GRACE_S` to `11.0`:
[modules/brain-model-manager.md](../../modules/brain-model-manager.md) answered that it still
contains `11` as a token of its own. Its only `11` is `~11 GB` in a sentence about how much VRAM a
still-dying cortex holds, far from anything about the grace. The reading is correct as written, and
a two-digit number is exactly the kind of value a document writes twice under two meanings. But a
reader told that a value is somewhere in a file, and not where, confirms or dismisses it with a
grep, which is the work the message was supposed to save.

Which line to quote has at least three answers: the first match, every match, or the match nearest
where the longest matched run stops. The third is the interesting one, because it is the only one
that uses what the message already computed.

## History

- 2026-08-24: opened by the close of
  [R-398](398-a-rendered-integer-is-a-token-inside-a-decimal.md), whose live proof of the decimal
  guard turned up a second file answering yes for a reason no matcher can rule out.
- 2026-08-25: closed as all three parts, the third option among them. A yes now says how many
  places contain the value, which one it read, and what that line says: the occurrence nearest
  where the matched run stops, by line number, read back windowed to a hundred characters and
  marked at whichever end it was cut. The entry's own case is sharper than it recorded. Replayed
  live, the `~11 GB` in
  [modules/brain-model-manager.md](../../modules/brain-model-manager.md) is 71 lines from the
  search text's own line rather than a hundred, and it sits one line above a sentence that names
  `stop_grace_s`, so proximity was never going to settle that case and the line's own words had to
  be quoted. That decided the shape: nearest is a tie break between matches and the quote is the
  answer. Two degenerate cases are recorded rather than fixed, a search text opening with its own
  value having no shape in front of it to be nearer to, and a file containing no part of the search
  text having no run at all; each falls back to the first occurrence by name. Six planted
  mutations, each caught, over 868 tests in the scripts suite, with the live replay of the case
  that opened this beside it. One residue: the run's own line is still never named, though the
  choice between matches is made by computing it
  ([R-426](426-the-run-is-reported-without-a-line-of-its-own.md)).
