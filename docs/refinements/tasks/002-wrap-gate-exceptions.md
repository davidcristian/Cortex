# Three exceptions the wrap gate did not ship

**Status:** landed 2026-08-09
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-07-19 behind the landing. The entry above named four things a hard wrap must not
touch, a URL, a pasted command, a fenced code block, and a `BREAKING CHANGE:` footer, and called deciding them
"the whole reason this is not a two-line patch". Only the first is covered, because the shipped
exemption is a property of the longest **word** rather than of the line's **kind**, and a pasted
command or a fenced line is built out of ordinary short words. Measured against the shipped gate
on 2026-07-19 rather than reasoned about: one message carrying an indented
`docker compose --project-directory . -f docker/docker-compose.yml ... up -d` line (108 chars,
longest word 29), a fenced `uv run pytest packages/core --cov ...` line (82 chars), and a
`BREAKING CHANGE:` footer of short words (118 chars) drew three complaints and exit 1. The
footer is the most serious of the three, because [AGENTS.md](../../../AGENTS.md) itself mandates
that footer for a breaking change, so the gate can now reject a message the commit rules require;
it is also the easiest of the three to live with, since a footer is prose and its value may legitimately carry
newlines, so it can simply be wrapped. A command and a fence cannot: reflowing either changes
what it says, which is the "rewriting messages rather than checking them" failure the entry
named. **What would close it:** a line-kind exemption rather than a word-width one, which is a
fence toggle carried through the walk plus a heuristic for a pasted command (a leading indent, a
shell prompt), and the decision about whether a footer is exempt at all or simply wrapped like
any other prose. **Trigger:** the first commit that genuinely needs a command or a block in its
body, at which point the author chooses between mangling the paste and bypassing the hook, which
is precisely the outcome the entry above was recorded to avoid. Until then the gate passes every
message this repo has actually written.

**Landed 2026-08-09, ahead of its trigger and not by it**
([ADR-0026 line-kind addendum](../../adr/ADR-0026-prose-style-gates.md)). No commit had yet needed
a command or a block in its body: over 433 commits the history holds 0 fenced lines, 0
prompt-marked lines and 0 `BREAKING CHANGE:` footers, so what moved this was the backlog being
worked rather than an author meeting the wall. **What it became:** `check_widths` in
`scripts/commitlint.py`, which is the width rule lifted out of the per-line walk into a walk of
its own, because a kind exemption needs state a single line cannot carry. A line between two
fences is not measured, either fence character opening and closing and an info string still
opening; a line whose first token is a bare `$` is not measured; and a fence still open when the
walk ends is a violation naming the line that opened it, since the alternative is one stray fence
exempting the rest of the message while the gate exits 0.
**The footer is not exempt: it wraps like the prose it is**, which is the decision this entry
left open, argued from what the footer is rather than from convenience. Its token is machine
read and its value is prose, and neither reader loses anything to a newline: git's trailer token
admits no space, so `BREAKING CHANGE:` is not a git trailer at all (`interpret-trailers --parse`
prints nothing for it and prints `Co-authored-by:` from the same message), and the Conventional
Commits parser that does read it allows a footer value to carry newlines. Exempting it would
remove the wrap from the one class of text the wrap is for, keyed on a token rather than on the
words.
**Two of this entry's own claims did not survive the measurement.** The first is the more serious:
the gate cannot "reject a message the commit rules require", because what it rejects is a footer
written unwrapped, and AGENTS.md mandates the footer and the wrap on the same page while the
specification it cites permits both at once. Proven against the gate as it stood that morning,
before anything was changed: a 139-character one-line footer exits 1 and the same footer wrapped
over lines of 63, 63 and 11 exits 0. The second is the pasted-command heuristic, which this entry
and its ADR both sketched as "a leading indent, a shell prompt". The indent half was tested
against this repo's own history and is false here: all 9 body lines indented four spaces or more
are prose, nested bullet continuations in two messages, the one that wired the Tauri shell and
one reporting VRAM measurements per model, so an
indent-based exemption would have unwrapped ordinary sentences and exempted nothing that exists.
Only the prompt shipped. **What this opens** is the entry below.

## Trail

- 2026-07-19: Opened behind the wrap gate's landing and replaced its own parent in the
  fix-when-it-bites bucket, because the exemption that shipped is a property of the longest word
  rather than of the line's kind, so a pasted command, a fenced block and a `BREAKING CHANGE:`
  footer of short words were all rejected.
- 2026-08-09: Struck ahead of its trigger, no commit in 433 having needed a command or a block in
  its body. The wrap walks the message carrying a fence toggle, steps over a fenced line and over
  a `$` prompted paste, and reports a fence left open rather than letting one exempt every line
  after it. The footer was decided rather than exempted, and the leading-indent half of the
  entry's own heuristic was rejected on this repo's history, where all 9 indented body lines are
  prose. What replaced it is the entry on a paste's reach.
