# Commit body 72-column wrap check

**Status:** done 2026-07-19
**Area:** repo-checks
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-checks.md)

[AGENTS.md](../../../AGENTS.md) says a commit body is wrapped at 72 columns, but
`scripts/commitlint.py` only measured the header (`MAX_HEADER_LENGTH = 72`). Nothing read the
body. On 2026-07-18 all seven of the most recent commits had body lines past 72, the worst at 77.

The fix is one more rule in the walk that already reads every line for dashes and volatile
references, plus a decision about the lines a hard wrap must not touch: a URL, a pasted command, a
code fence, and a `BREAKING CHANGE:` footer can all legitimately run past 72.

Closed by adding `MAX_BODY_WIDTH = 72` to `scripts/commitlint.py`, measured on every line below
the header. The header keeps its own limit so one long subject produces one complaint rather than
two. One exception was added: a line past the wrap whose longest single word is itself longer than
the wrap has nowhere to break, so a URL, a path or a long identifier is allowed, while ordinary
prose past the wrap is not. Checked against the four 73-character lines already on master and
against bodies that are correctly wrapped. The other three exceptions are
[R-002](002-wrap-gate-exceptions.md).

## History

- 2026-07-18: Opened after a review measured the problem instead of assuming it. Every one of the
  seven most recent commits had body lines past 72, the worst at 77.
- 2026-07-19: Closed. `scripts/commitlint.py` now measures every line below the header against
  `MAX_BODY_WIDTH = 72`, inside the walk that already read each line for dashes and volatile
  references.
