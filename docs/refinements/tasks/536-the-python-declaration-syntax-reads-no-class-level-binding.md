# The Python declaration syntax reads no binding inside a class body

**Status:** open, dead until a consumer
**Area:** repo-gates
**Trigger:** a second producer binding a `SourceKind` value at module level because the enum
member it restates cannot be a site, which the `uri` twin's producer would be, or any other
registry entry whose one spelling on a side is a member of a class body.
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-02 by the close of
[534](534-the-declared-kind-word-has-no-site-to-hold-it.md), which held the kind word `sender` by
binding it at module level in `cortex_email/server.py` and mentioning the enum member, and
recorded why the other road was not taken.

The Python form in `crosscheck.DECLARATIONS` opens with `^` under `re.MULTILINE` and takes the
name at column 0, so a binding inside any block is not a site. That anchor was chosen so a name
bound inside a function is never read as a second declaration of a module's constant, and it makes
every enum member in the brain unregistrable as a site. Today one entry needs one, and it is served
by a module-level twin at the producer: the sidecar binds `_SENDER_KIND = "sender"` and the member
`SENDER = "sender"` is a mention rendering name and value. That twin is one commented binding the
gate holds to the member, so nothing is unheld; the cost is a spelling of the word that exists for
the scan's sake.

**Why it was left.** An indented form has to tell a class body from a function body, and the two
look the same on their own line. A pattern found by `findall` cannot do it; a reader that walks
lines with an indentation stack is a new module with its own suite and its own faults, among them a
member spelled in two classes of one file, a class nested in a function, and a member whose
right-hand side is a call rather than a literal. Landing that for one entry would be the registry
growing a parser to save one binding.

**What would close it.** A class-level form that is a second reader rather than a widened pattern:
given a path and a dotted name (`SourceKind.SENDER`), find the `class` line at some indentation,
then the member one level deeper before the next line at the class's own indentation, and hand its
right-hand side to `parse_value`. `Site.name` would carry the dotted form, so a bare name keeps
meaning column 0 and no entry registered today changes meaning. The mutation is the one the parent
task ran: rename the member's value alone and watch the gate fail naming both files. When it lands,
the module-level twin at the producer can go or stay; a second site is a stronger reading than a
mention, since two sites are compared with each other while a mention is a presence check.

## Trail

- 2026-09-02: opened by the close of
  [534](534-the-declared-kind-word-has-no-site-to-hold-it.md), whose ADR-0029 declared-kind-word
  addendum records why the narrow road was taken.
