"""Every model artifact this tree names, and the variable each one is named under.

`flagcheck.py` holds every subagent server this repo starts to the flags its tier requires, and
both readers of that set answer "is this one" out of a single string, the `MODEL_PREFIX` of
`subagentservers.py`: a compose command spends a variable beginning that way, or a hosted tier's
`model_path` is aliased to one. That reading is exact for the artifacts written down today and
says nothing about the one written tomorrow. A subagent artifact named
`CORTEX_SUBAGENT_MODEL_FILE_CPU` is the same artifact under a variable neither reader looks at, so
the server or tier it names leaves both sets in silence and reddens nothing.

**This module answers the question underneath that one.** Not "what does this declaration say",
which is what the two set readers ask, but "is every declaration of this kind spelled so that it
can be found at all". It returns every model artifact the tree names, in both places one is named,
and the rule in `flagcheck.py` holds each to beginning `subagentservers.FAMILY_PREFIX`, which is
the whole of what makes the membership reading above it decidable.

**The artifacts are found structurally, never by the prefix.** A rule whose domain was the
variables that already begin `CORTEX_MODEL_FILE_` would be a rule about the very convention it
checks: the misspelling it exists to catch is outside that domain by construction, so it could
not fail for the one fault it was built for. A compose artifact is therefore the item after
llama.cpp's own `--model`, and a hosted one is the settings field a tier reads its `model_path`
from, which is the reading `hostedtiers.py` already makes with its subagent filter turned off.

**The short spelling of the model flag is deliberately not read.** llama.cpp accepts `-m`, and
this tree starts an MCP sidecar with `python -m <module>`: a reader taking the item after every
`-m` as a model artifact would call a module name one and redden a correct service whose only
remedy would be to teach the gate, which is worse than the miss it would close. Every server
started here spells the flag in full, and a server that did not would still be found by the
wiring that dials it.

**An item that spends no variable names nothing this rule can hold.** A model path written out in
full carries no name to misspell, and the membership readers already have their own answer for
that shape. So does a server whose artifact reaches it through its environment rather than its
argv: this reads what a command names, and the model host's own tiers are read from the sidecar's
declaration rather than from the passthrough that feeds it.

**A server that serves no chat still names an artifact this rule holds.** The CPU embedder runs
from the same llama.cpp image as the subagent servers, and what it serves is `subagentservers.py`'s
question rather than this one: that reader keeps it out of the subagent set on its own, by the
variable its argv spends and by a wiring that never dials it. This reader asks the question
underneath, whether an artifact is spelled so such an answer is decidable at all, and an argv
declaring `--embeddings` is spelled no differently from any other. So there is no embedding
exclusion here, and the one that used to sit here excused the single artifact in this tree spelled
outside the family, in the very block a new non-chat model server would be copied from
(ADR-0029's addendum on a non-chat artifact naming itself in the family).

**No floor of its own is asserted, because one is asserted underneath.** `hostedtiers.py` refuses
a sidecar declaring no tier and a tier naming no artifact, so a tree this reader can read at all
names at least one artifact, and a reading that answered emptily forever is already impossible.
"""

from pathlib import Path
from typing import NamedTuple

from composedefaults import SubstitutionReadError, read_line
from composefiles import compose_files
from composestarts import ComposeStartError, Started, read_starts
from hostedtiers import (
    MODEL_MANAGER,
    TIER_MODULE,
    aliases,
    declared,
    parse_module,
    tier_artifacts,
)

# llama.cpp's own flag naming the artifact a server serves, in the long spelling every server
# started here writes and the only one this reader takes.
MODEL_FLAG = "--model"


class Artifact(NamedTuple):
    """One model artifact this tree names, and the variable a deployment names it under.

    ``where`` is the compose service whose argv names it, or the settings field a hosted tier
    reads its path from, which is the word an author would search the file for. ``line`` is where
    that declaration opens rather than where the name itself is written, the service or the tier,
    which is the line the substitution reader is handed for its own refusals.
    """

    file: str
    where: str
    line: int
    variable: str


def spends(started: Started) -> tuple[str, ...]:
    """Every variable one service's argv names a model artifact under, in the order written."""
    command = started.command or ()
    try:
        return tuple(
            spend.name
            for index, item in enumerate(command)
            if item == MODEL_FLAG and index + 1 < len(command)
            for spend in read_line(started.line, command[index + 1])
        )
    except SubstitutionReadError as err:
        msg = f"the command of {started.service!r} cannot be read: {err}"
        raise ComposeStartError(msg) from err


def _read(path: Path) -> str:
    """Read one compose file, naming it when it is absent or is not text."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {path}: {err}"
        raise ComposeStartError(msg) from err


def composed(root: Path) -> tuple[Artifact, ...]:
    """Every artifact a compose command under ``root`` names, in the order the tree is walked."""
    return tuple(
        Artifact(
            file=path.relative_to(root).as_posix(),
            where=started.service,
            line=started.line,
            variable=variable,
        )
        for path in compose_files(root)
        for started in read_starts(_read(path))
        for variable in spends(started)
    )


def tiered(root: Path) -> tuple[Artifact, ...]:
    """Every artifact the model host's own tiers name, the subagent tier and the rest alike."""
    module = parse_module(root, TIER_MODULE)
    named = aliases(module)
    shown = (MODEL_MANAGER / TIER_MODULE).as_posix()
    return tuple(
        Artifact(file=shown, where=field, line=call.lineno, variable=variable)
        for call in declared(module)
        for field, variable in tier_artifacts(call, named)
    )


def named(root: Path) -> tuple[Artifact, ...]:
    """Every model artifact the tree under ``root`` names, the compose commands first."""
    return (*composed(root), *tiered(root))
