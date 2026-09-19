# Three exceptions the wrap check did not include

**Status:** done 2026-08-09
**Area:** repo-checks
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-checks.md)

[R-001](001-commit-body-wrap-check.md) named four kinds of line a hard wrap must not touch: a URL,
a pasted command, a fenced code block, and a `BREAKING CHANGE:` footer. Only the URL was covered,
because the exception it added is a property of the longest word rather than of the kind of line,
and a pasted command or a fenced line is built from ordinary short words. Measured against the
committed check on 2026-07-19: an indented
`docker compose --project-directory . -f docker/docker-compose.yml ... up -d` line (108
characters, longest word 29), a fenced `uv run pytest packages/core --cov ...` line (82
characters) and a `BREAKING CHANGE:` footer of short words (118 characters) produced three
complaints and exit 1.

Closed 2026-08-09, before any commit needed it: over 433 commits the history contains 0 fenced
lines, 0 prompt-marked lines and 0 `BREAKING CHANGE:` footers. The width rule moved out of the
per-line walk into `check_widths` in `scripts/commitlint.py`, because recognising a kind of line
needs state that a single line does not have. A line between two fences is not measured, either
fence character opening and closing it and an info string still opening one; a line whose first
token is a bare `$` is not measured; and a fence still open when the walk ends is a violation that
names the line which opened it, so one stray fence cannot exempt the rest of the message.

The footer is not exempt and wraps like the prose it is. Its token is read by machine and its
value is prose, and neither reader loses anything to a newline: git's trailer token allows no
space, so `BREAKING CHANGE:` is not a git trailer (`interpret-trailers --parse` prints nothing for
it and prints `Co-authored-by:` from the same message), and the Conventional Commits parser that
does read it allows a footer value to contain newlines.

Two claims in the original entry turned out to be wrong. The check cannot reject a message the
commit rules require: what it rejects is a footer written unwrapped, and AGENTS.md requires the
footer and the wrap together, which the specification permits. Measured before anything changed: a
139-character one-line footer exits 1, and the same footer wrapped over lines of 63, 63 and 11
exits 0. The other wrong claim is the sketch of a pasted-command test as "a leading indent, a
shell prompt". The indent half is false here: all 9 body lines in this repo indented four spaces
or more are prose, nested bullet continuations in two messages, so an indent-based exception would
have unwrapped ordinary sentences and exempted nothing. Only the prompt was added. The remaining
question is [R-003](003-paste-exemption-reach.md).

## History

- 2026-07-19: Opened after the wrap check was added, because its exception is a property of the
  longest word rather than of the kind of line, so a pasted command, a fenced block and a
  `BREAKING CHANGE:` footer of short words were all rejected.
- 2026-08-09: Closed before any of 433 commits needed a command or a block in its body. The width
  rule now walks the message tracking whether a fence is open, steps over a fenced line and over a
  `$` prompted paste, and reports a fence left open instead of exempting every line after it. The
  footer was decided rather than exempted, and the leading-indent half of the entry's own test was
  rejected against this repo's history, where all 9 indented body lines are prose. What replaced it
  is the entry on how far a paste exemption reaches.
