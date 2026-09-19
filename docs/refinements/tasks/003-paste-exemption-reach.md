# How far the paste exemption reaches

**Status:** done 2026-08-09
**Area:** repo-checks
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-checks.md)

Once a commit body may contain a paste, how far that exemption reaches becomes a decision rather
than an oversight. [R-002](002-wrap-gate-exceptions.md) exempted a paste from the width rule only:
inside a fence and after a `$` prompt, the dash ban, the volatile-reference ban and the
resolving-hash check still read every line. Measured on the committed check with one fenced
message: `cargo llvm-cov -- --nocapture` produced `line 5 uses a spaced ASCII --`, and a
`git show` of a short hash that really resolves produced `line 4 cites commit`. Two complaints and
exit 1 over a paste that is correct both times, since `--` is cargo's own argument separator and
the hash is the command's argument rather than a citation.

Closed the same day, before a commit needed it: over 437 commits the history contains 0 fenced
lines and 1 prompt-marked line, the `docker compose` paste from hours earlier, which has neither a
bare `--` nor a hex token. What moved it is that the commands this repo would paste are its own
check invocations: the `justfile` runs `cargo clippy ... -- -D warnings` twice and
`cargo test ... -- --ignored --nocapture` once, with the same form in two runbooks.

The answer is per rule. `classify_lines` in `scripts/commitlint.py` is the fence tracking and the
prompt test lifted out of the width rule into one classification that the width rule and the prose
rules both use, so the file has a single definition of where a block begins and ends. A paste is
exempt from the width rule and from the dash ban, and from nothing else. The width rule and the
dash ban are about the text as typed, and the dash ban is specifically about a dash used as
punctuation, which verbatim text does not do; its remedy, restructuring the sentence, does not
exist for words the author did not write. The volatile-reference ban and the resolving-hash check
are about the message's future rather than its typing, so who produced the characters does not
matter, and their remedy survives a paste: `git show <sha>` still gives everything the original
gave, where a reflowed command gives less.

The narrower option, exempting only the argument separator `--` and a hash inside a fence, was
rejected: a rule that exempts ASCII `--` inside a paste while still banning an em dash there is a
rule about character sets rather than kinds of line, and it fails on pasted program output, which
can contain one.

Checked against the previous commit's version of the checker before being used: a fenced
`cargo llvm-cov -- --nocapture` exits 1 there, the same behind a `$` prompt exits 1, and a fenced
em dash exits 1, while all three exit 0 now. The limits were measured too: the same separator
unfenced exits 1, after the fence closes exits 1, and on the line after a `$` prompt exits 1; an
unclosed fence still exits 1 naming the line that opened it; and inside a fence a `git show` of a
resolving short hash and a `grep -n 'ADR-0026'` each still exit 1.

Two residues are accepted costs rather than new work, and are written beside the behaviour in the
ADR: a fence around prose exempts it from the dash ban, and a paste of `git log --oneline` output
is rejected for being all hashes.

## History

- 2026-08-09: Opened after the line-kind exemption was added, because inviting a paste into a
  commit body makes the reach of the other three rules a decision.
- 2026-08-09: Closed later the same day, before any commit needed it. Over 437 commits the history
  contains 0 fenced lines and 1 prompt-marked line, which has neither a bare separator nor a hex
  token, so what moved it is that the next paste was close. A paste is exempt from the width rule
  and the dash ban and from nothing else, and the entry's own narrower option was rejected for
  being a rule about character sets rather than kinds of line.
- 2026-09-19: A third rule joined the two. The body is now at most 50 words, and the count leaves
  out the same pasted lines, so a mutation table keeps its rows without spending the budget.
