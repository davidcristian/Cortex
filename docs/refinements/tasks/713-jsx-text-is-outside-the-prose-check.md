# JSX text is outside the prose check

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Trigger:** a label written as text between JSX tags in a non-test overlay component holds a word
from the table in AGENTS.md.
**Verified:** 2026-09-23

The prose check reads the string literals of the non-test Rust and TypeScript files under `body/`
(decision 16 of [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)), through the lexer in
`scripts/slashcomments.py`. Text between JSX tags is not a string literal, so that lexer reads it
as code, and a label such as `<p className="empty-line">Ask me anything</p>` in
`body/app/src/components/ChatView.tsx` is never searched. On 2026-09-23 a grep for two or more
words between tags on one line found four such labels in non-test components, in `ChatView.tsx`,
`Reminders.tsx`, `SessionRow.tsx` and `ShortcutsTab.tsx`, and a search of every non-test `body/`
file for the table's words found none outside identifiers, comments and string literals.

**What would close it.** A reader that tells JSX text from a `<` comparison or a type argument. The
lexer knows no JSX, so this needs either a small TSX-aware scanner in `scripts/` with its own tests
or a parser dependency, and the result joins `proseliterals.slash_literals`.

## History

- 2026-09-23: opened when R-711 extended the literal reader to Rust and TypeScript and left JSX
  text outside it.
