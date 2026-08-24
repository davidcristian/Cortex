"""The environment a gate's git call runs with, in the one place every caller reads it from.

Three gates here ask git something: `bindcheck.py` whether a path is tracked and whether it is
ignored, `commitlint.py` whether a token resolves to a commit, `dashcheck.py` which paths git
ignores under a root. Each passes `-C <root>` to say which repository it means, and each runs
inside a git hook whenever `just check` runs from pre-commit. Git exports its own variables to a
hook, and `GIT_DIR` outranks `-C`: a call that inherits one answers about whatever repository git
is mid-commit in, and the answer is well formed, so nothing downstream can tell. That is the
failure this module exists to have one home for.

**The environment is shared and the call is not.** The three ask different questions and want
different answers to a non-zero exit: `check-ignore` says 1 for a legitimate no, `ls-files` says 1
for nothing at all, and `commitlint.py` treats a git it cannot run as "cannot disprove the hash"
rather than a failure, because blocking a commit on a missing git would be the wrong trade there.
A shared runner would grow a parameter per caller and hide three different policies behind one
signature; a shared environment is one fact with one reason, and each gate keeps its own argv.

**The suites read this too**, deliberately. Their fixtures drive a real `git` against a temporary
repository for the reason the gates do, so a fixture that rebuilt the environment by hand could
drift from the gate it tests, and the drift would be invisible in exactly the same way: the
fixture's `add` would land in the in-flight commit's index rather than the fixture's.

Everything git exports is dropped rather than `GIT_DIR` alone. `GIT_WORK_TREE`, `GIT_INDEX_FILE`
and `GIT_OBJECT_DIRECTORY` each redirect part of the same answer, and a gate asking about a root it
names has no use for any variable git set for a hook. The prefix ends in its underscore, so a
`GITHUB_*` variable a CI runner sets is not git's and stays.
"""

import os

GIT_PREFIX = "GIT_"


def git_env() -> dict[str, str]:
    """Return the ambient environment with every variable git exports to a hook removed."""
    return {key: value for key, value in os.environ.items() if not key.startswith(GIT_PREFIX)}
