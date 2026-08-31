"""Which directory components no walk in this tree enters, in the one place all of them read.

Four walks here prune the same trees before they read anything: `dashcheck.py` over every text
file, `linecap.py` over three toolchains' source, `backloganchors.py` over the repo's markdown,
and `composefiles.py` over the compose files. They ask different questions and none of the
answers is about a dependency's tree, a build output or a tool's cache, so the names live here
and no walk spells them twice. `linecap.py` adds two of its own, and that addition lives with the
reason for it rather than here.

**This list is deliberately not `.gitignore`, and the overlap with it is measured rather than
believed.** Eight of the ten names below are ones git ignores wherever they appear, so for those
eight this list restates a rule git already applies. The other two are why it cannot become git's
answer:

- `.git` is not part of the work tree, so git never reports it as ignored. A walk that trusted
  the ignore listing alone would descend into the object database.
- `coverage` is ignored only under `body/app/`, by that tree's own `.gitignore`. A `coverage/`
  at the root or under `brain/` is ignored by nothing, so skipping it is this list's doing and
  nobody else's.

The other three walks deliberately do not ask git. The dash ban does ask, and its collection is
git's answer (the ADR-0026 dash-ban-collection addendum). Teaching the rest would make the line
cap, the anchor scan and the compose walk all fail on a root git cannot answer about, which would
stop `just check` running outside a git working tree: an export, an unpacked archive, a vendored
copy of this repo. That narrows three gates to remove a redundancy in eight names, and the eight
are cheap. Pruning by name also happens before any question is asked, which is what keeps a walk
out of an ignored bind target rather than merely quiet about it.

So the redundancy stays on purpose, and the suite beside this module compares the two: it measures
every name against git's own answer for this repo, so a name that stops being a restatement, or
starts being one, is reported.
"""

# Vendored trees, build output, tool caches, and the object database. Ten names, of which eight
# also appear in a `.gitignore`; the two that do not are argued above.
SKIPPED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        ".claude",
        "target",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "coverage",
    }
)
