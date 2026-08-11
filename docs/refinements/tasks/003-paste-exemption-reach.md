# Paste exemption limited to the wrap

**Status:** landed 2026-08-09
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-09 behind the landing above, because inviting a paste into a commit body makes the other
three rules' reach a decision rather than an absence. The kind exemption is width only: inside a
fence and after a `$` prompt, the dash ban, the volatile-reference ban and the resolving-hash
check still read every line. Measured on the shipped gate rather than reasoned about, with one
fenced message: `cargo llvm-cov -- --nocapture` draws `line 5 uses a spaced ASCII --` and a
`git show` of a short hash that really resolves draws `line 4 cites commit`, two complaints and
exit 1 over a paste that is correct in both cases, since `--` is cargo's own argument separator
and the hash is the command's argument rather than a citation. It waits because the width rule is
the one this repo measured drift against and because the other three are not obviously wrong
here: a hash pasted into a body still stops resolving after a rewrite, and a message is still
prose. **What would close it:** either the same kind toggle carried into the dash and hash checks,
which is the walk it was just lifted out of and a decision that a paste is not the author's prose,
or the narrower reading that only the argument-separator `--` and a hash inside a fence are
exempt. **Trigger:** the first commit whose paste carries either, at which point the author
chooses between mangling the paste and bypassing the hook, which is exactly the outcome the entry
above exists to prevent.

**Landed 2026-08-09, ahead of its trigger, and the narrower of the two readings it offered was
refused** ([ADR-0026 paste-reach addendum](../../adr/ADR-0026-prose-style-gates.md)). **The trigger
had not fired and is reported rather than glossed:** over 437 commits the history holds 0 fenced
lines and 1 prompt-marked line, that one being the `docker compose` paste in the commit that
shipped the kind exemption hours earlier, and it carries neither a bare `--` (its dashes are all
attached flags) nor any hex token. What moved this is that the wall is one paste away rather than
hypothetical, the facility now being in use and the commands this repo would paste being its own
gate invocations: the `justfile` runs `cargo clippy ... -- -D warnings` twice and
`cargo test ... -- --ignored --nocapture` once, with the same shape in two runbooks.
**What it became:** a per-rule answer. `classify_lines` in `scripts/commitlint.py` is the fence
toggle and the prompt test lifted out of the wrap into one classification both the wrap and the
prose rules consume, so the file holds a single answer to where a block begins and ends. A paste
is exempt from the wrap and from the dash ban, and from the volatile-reference ban and the
resolving-hash check it is not. **The argument is what each rule is for rather than which is
convenient.** The wrap and the dash ban are about the text as typed, and the ban is specifically
on a dash used as punctuation, which verbatim text does not do: `--` in
`cargo llvm-cov -- --nocapture` is cargo's argument separator, and the rule's own remedy,
restructuring the sentence, does not exist for words the author did not write. The other two are
about the message's future rather than its typing, so who produced the characters is beside the
point, and their remedy survives a paste intact, `git show <sha>` carrying everything the
original carried where a reflowed command carries less.
**This entry's own narrower reading was refused**, that only the argument-separator `--` and a
hash inside a fence be exempt: a rule that exempts ASCII `--` inside a paste while still banning
an em dash there is a rule about character sets rather than kinds, and it fails on pasted program
output, which can carry one and which an author would then have to alter. All three banned forms
go, and the signal stays the author's declaration that the width exemption already reads.
**Proven able to fail before being trusted, with the defect reproduced first on the checker
exactly as it stood at the previous commit:** a fenced `cargo llvm-cov -- --nocapture` exits 1
there, the same behind a `$` prompt exits 1, a fenced em dash exits 1, and all three exit 0 now.
The leaks were measured, not assumed: the same separator unfenced exits 1, after the fence closes
exits 1, and on the line after a `$` prompt exits 1; an unclosed fence still exits 1 naming the
line that opened it; and inside a fence a `git show` of a resolving short hash and a
`grep -n 'ADR-0026'` each still exit 1. **No new deferral opens**, which is a decision: the two
residues, that a fence around prose launders it past the dash ban the way it already launders it
past the wrap, and that a paste of `git log --oneline` output is refused for being all hashes,
are the accepted costs of an author-declared exemption and of the column above, written beside
the behaviour in the ADR rather than filed as work.

## Trail

- 2026-08-09: Opened behind the line-kind landing as the same exemption read to its edge, since
  inviting a paste into a commit body makes the other three rules' reach a decision rather than an
  absence.
- 2026-08-09: Struck later the same day, ahead of its trigger, taking the area from six entries to
  five. Over 437 commits the history holds 0 fenced lines and 1 prompt-marked line, which carries
  neither a bare separator nor a hex token, so what moved it is that the wall is one paste away.
  The answer is per rule: a paste is exempt from the wrap and from the dash ban and from nothing
  else, and the entry's own narrower reading was refused for being a rule about character sets
  rather than kinds.
