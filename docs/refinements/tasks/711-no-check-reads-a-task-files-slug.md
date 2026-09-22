# No check reads a task file's slug

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-22

A task file is `NNN-slug.md`, and `scripts/backlog.py` checks only that the slug is lowercase words
joined by hyphens. The slug is written from the title, and `prosecheck.py` reads the title, so a
new slug starts free of the banned words in AGENTS.md. A word added to that table later is found
in every title and in none of the slugs, which is how 97 slugs came to use one before R-700 renamed
them.

**What would close it.** Make `backlogcheck.py` report a slug that contains a banned word, reading
the table and matching it through `scripts/bannedwords.py` with the slug's hyphens read as spaces,
the way the R-700 survey did. A word added to the table then fails the check until the files that
use it are renamed and their links rewritten.

## History

- 2026-09-22: opened by R-700, whose rename left nothing to find a banned word in a slug the next
  time the table grows.
