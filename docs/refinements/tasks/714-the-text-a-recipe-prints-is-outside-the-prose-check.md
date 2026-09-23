# The text a recipe prints is outside the prose check

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-23

The prose check reads the comments of the justfile and the shell scripts, and the string literals
of Python, Rust and TypeScript (decision 16 of
[ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)). It never reads the text a recipe or a
script passes to `echo` or `printf`, although an operator reads that text the same way as a
check's failure line. On 2026-09-23 the `replay` recipe printed three words from the table: the
bodies `landed since` a date, a ledger that `carries no commit`, and `no standing count`. Those
lines are rewritten, and a grep of the justfile and every tracked `*.sh` file for an `echo` or a
`printf` holding a table word now finds none.

**What would close it.** A reader for the double-quoted strings in the justfile's recipe bodies and
in the `*.sh` files, joining the literals `proseliterals.py` already returns, with a test that a
table word inside an `echo` is reported and one inside a `$variable` or a flag is not; or a sentence
in decision 16 saying why shell text stays out.

## History

- 2026-09-23: opened while [R-705](705-names-inside-files-still-use-banned-words.md) renamed the
  `verdict` family and found the same words in the replay recipe's output.
