# The Python declaration syntax reads no binding inside a class body

**Status:** open, waiting for a consumer
**Area:** repo-checks
**Trigger:** a second module binding a `SourceKind` value at module level because the enum member it
repeats cannot be a declaration, which a producer of the `uri` kind would be; or any other registry
entry whose only copy of a value on one side is a member of a class body. Count those by searching
each mention's text in its target file and checking whether the matching line assigns a name inside
a `class`.
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)
**Verified:** 2026-09-19

The Python pattern in `crosscheck.DECLARATIONS` starts with `^` under `re.MULTILINE` and takes the
name at column 0, so a binding inside any block is not a declaration. That anchor stops a name bound
inside a function from counting as a second declaration of a module constant, and it also makes
every enum member in the brain unregistrable. One entry needs one today, and it is served by a
module-level copy at the producer: the sidecar binds `_SENDER_KIND = "sender"` and the member
`SENDER = "sender"` is compared against it, so nothing is unchecked. The cost is one copy of the
word that exists for the check's sake.

**Why it was left.** A pattern found with `findall` cannot tell a class body from a function body,
since the two look the same on their own line. A reader that walked lines with an indentation stack
would be a new module with its own tests and its own faults: a member defined in two classes of one
file, a class nested in a function, a member whose value is a call.

**What would close it.** A second reader rather than a wider pattern, and it no longer needs a
parser of its own. `scripts/moduleconstants.py` already parses a module with `ast` without importing
it and its `bound` handles both assignment forms, and `scripts/settingsfields.py` already walks the
statements of each top-level class body. Given a path and a dotted name (`SourceKind.SENDER`), take
the one `ClassDef` of that name in the module's own body, the one statement `bound` says assigns the
member, and pass the source of its right-hand side to `parse_value`, so a call there raises exactly
as it does at column 0. Walking only the module's top level handles the class nested in a function,
and requiring exactly one match handles the member defined in two classes. `Site.name` would hold
the dotted form, so a bare name keeps meaning column 0 and no entry registered today changes
meaning. To prove the fix works: rename the member's value alone and watch the check fail naming
both files. Afterwards the module-level copy at the producer can go or stay, since two declarations
are compared with each other while a mention is only a presence check.

## History

- 2026-09-02: opened by the close of [534](534-the-declared-kind-word-has-no-site-to-hold-it.md),
  whose ADR-0042 entry records why the narrow way was taken.
- 2026-09-04: checked and left open, neither condition met. `cortex_email/server.py` is still the
  only module outside the core that writes a `cortex/source` declaration, and the `URI` member has
  no producer. Searching all 288 of the registry's mention texts in their target files finds one
  assignment inside a class body, `SENDER = "sender"` under `class SourceKind`, this entry's own
  subject. `Flag("--reasoning-budget", "0")` in `scripts/flagcheck.py` looks like a near miss and is
  not one: it sits in a module-level tuple, and that entry declares its value at
  `_NO_REASONING_BUDGET` in the model host's config.
- 2026-09-13: checked again and left open. The registry has grown to 92 entries over 110
  declarations and 311 mentions, and the same single assignment inside a class body is the only one,
  in `brain/packages/core/src/cortex_core/provenance.py`. `SourceKind` still has one producer
  outside the core and `URI` still has none. `crosscheck.DECLARATIONS` is unchanged.
- 2026-09-19: checked again and left open, with the fix made cheaper. The registry holds 92 entries
  over 110 declarations and 313 mentions, and reading each mention's target file with `ast` finds
  the same single assignment inside a class body. What moved is the cost:
  `scripts/settingscheck.py`, added on 2026-09-17, reads settings classes through
  `settingsfields.py`, which parses a module with `moduleconstants.parse` and walks each top-level
  class body, so the class-level reader is a few lines over existing code rather than a new parser.
  That scan is not a consumer, since it reads field names and their environment variables and never
  a value the registry compares.
