# The reading that says a file still spells a value does not say where it read one

**Status:** landed 2026-08-25
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-24 by the close of
[R-398](398-a-rendered-integer-is-a-token-inside-a-decimal.md), which removed the decimal case of
this misreading and could not remove the homonym one.

When a rendered needle is unfound, `needles.unfound` adds the reading that decides who the fault is
about: whether the file **still spells this constant's own value** as a token of its own, which is
the evidence that what moved is shape and the entry named is not the entry to change (ADR-0023
misattributed-fault addendum). It searches the bare value across the whole file and reports a
yes or a no. It never says which line the yes came from.

Measured live while R-398 was being closed, by retuning `DEFAULT_STOP_GRACE_S` to `11.0`:
[modules/brain-model-manager.md](../../modules/brain-model-manager.md) answered that it does still
spell `11` as a token of its own. Its only `11` is `~11 GB` in a sentence about how much VRAM a
still-dying cortex holds, a hundred lines from anything about the grace. The reading is correct as
written, the docstring already calls its conclusion a maybe, and a two-digit number is exactly the kind of
value a document spells twice under two meanings. But a reader who is told a value is still
somewhere in a file, and not where, confirms or dismisses it with a grep, which is the work the
fault was supposed to save.

**Why it was left.** R-398 was about the matcher's edges, and the decimal guard is the half of this
that a rule can decide. Which line to quote is a presentation question with at least three
answers (the first match, every match, or the match nearest the longest carried run), and the
third is the interesting one precisely because it is the only one that uses what the fault already
computed. Choosing inside a close about boundaries would have hidden it.

**What would close it.** Decide what a yes should quote, then quote it. The cheap version is the
line number of the first bounded match, which is one `text.count("\n", 0, match.start())` and turns
the grep into a jump. The version worth weighing against it is the line nearest the carried run,
since the two readings the fault already carries are about the same divergence and pointing them
at the same place is what makes them one sentence instead of two. Weigh also whether a yes with
many matches should say how many, since "spelled in eleven places" is itself the answer that the
reading proves nothing.

## Trail

- 2026-08-24: opened by the close of
  [R-398](398-a-rendered-integer-is-a-token-inside-a-decimal.md), whose live proof of the decimal
  guard turned up a second file answering yes for a reason no matcher can rule out.
- 2026-08-25: landed as all three parts, the third option among them. A yes now says **how many
  places** spell the value, **which one** it read, and **what that line says**: the occurrence
  nearest where the carried run stops, by line number, read back windowed to a hundred characters
  and marked at whichever end it was cut. **The entry's own case is sharper than it recorded.**
  Replayed live, the `~11 GB` in [modules/brain-model-manager.md](../../modules/brain-model-manager.md)
  is 71 lines from the needle's own line rather than a hundred, and it sits **one line above** a
  sentence that names `stop_grace_s`, so proximity was never going to settle that case and the
  line's own words had to be quoted. That is what decided the shape: nearest is a tie break between
  matches and the quote is the verdict. Two degenerate cases are recorded rather than fixed, a
  needle opening with its own value having no shape in front of it to be nearer to and a file
  carrying no part of the needle having no run at all, and each falls back to the first occurrence
  by name. Six planted mutations, each caught, over 868 tests in the scripts suite; tabled in the
  ADR-0029 still-spelled addendum, with the live replay of the case that opened this beside it.
  One residue: the run's own line is still never named, though the choice between matches is made
  by computing it
  ([R-426](426-the-run-is-reported-without-a-line-of-its-own.md)).
