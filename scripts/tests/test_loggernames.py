"""Behaviour of the reader that says which module owns the logger a brain line is written under.

The fixtures are miniature brain packages, laid out the way the real ones are (`<package>/src/`
holding an importable tree), because the walk's whole job is to find a logger by the name a
document prints and that name is a function of where the module sits. The last test here reads the
committed brain, where every spelling of a logger claim is true or this reader is answering about a
tree nobody ships.
"""

from pathlib import Path

import pytest

import logcalls
import loggernames
from moduleconstants import constants, parse
from skippeddirs import SKIPPED_DIRS

REPO_ROOT = Path(__file__).resolve().parents[2]

# The name a self-named sink binds its logger under, and the one thing the guard at the end of
# this file spells: WHICH sinks are self-named is read out of the tree rather than listed. The
# constant registry ties this to the sinks that write it, so the guard cannot be deleted in
# silence and a sink cannot rename its declaration away from the guard asking for it.
DECLARATION = "_LOGGER_NAME"

SETTLE = (
    '"""A miniature of the settler."""\n\nimport logging\n\n_logger = logging.getLogger(__name__)\n'
)


def brain(root: Path, files: dict[str, str]) -> None:
    """Write a miniature brain, each path relative to `brain/packages/`."""
    for relative, text in files.items():
        path = root / "brain" / "packages" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def settler(root: Path) -> None:
    """The one fixture package every test about the walk itself starts from."""
    brain(root, {"core/src/cortex_core/swap_settle.py": SETTLE})


def test_a_module_logging_under_name_is_found_by_its_dotted_path(tmp_path: Path) -> None:
    settler(tmp_path)
    assert loggernames.loggers(tmp_path) == {
        "cortex_core.swap_settle": "brain/packages/core/src/cortex_core/swap_settle.py"
    }


def test_a_sink_that_names_itself_is_found_under_the_name_it_chose(tmp_path: Path) -> None:
    """The spelling neither self-named sink writes any more, both binding the name above the call.

    It stays read because a ``getLogger("name")`` call is legal Python that a brain module may
    write tomorrow, and a reader that stopped matching one would drop that logger out of the
    answer in silence, which is worse than a spelling nothing currently exercises.
    """
    brain(tmp_path, {"tools/src/cortex_tools/audit.py": 'getLogger("cortex.tools.audit")\n'})
    assert set(loggernames.loggers(tmp_path)) == {"cortex.tools.audit"}


def test_a_sink_naming_its_logger_through_a_constant_is_found_under_that_name(
    tmp_path: Path,
) -> None:
    """The recall trail's spelling: its name is a declaration because three documents restate it
    and the constant registry ties them to it, so a reader that knew only a literal would drop
    that trail out of this answer and fail a sample of it as a logger no module declares."""
    brain(
        tmp_path,
        {
            "memory/src/cortex_memory/audit.py": (
                '_LOGGER_NAME = "cortex.memory.recall"\n_logger = logging.getLogger(_LOGGER_NAME)\n'
            )
        },
    )
    assert loggernames.loggers(tmp_path) == {
        "cortex.memory.recall": "brain/packages/memory/src/cortex_memory/audit.py"
    }


def test_a_logger_named_through_something_the_module_does_not_bind_is_a_fault(
    tmp_path: Path,
) -> None:
    """A name from anywhere but this module's own top level is refused rather than chased: an
    importer of the brain is what this tree may not become, so the fault says which name it is."""
    brain(
        tmp_path,
        {
            "memory/src/cortex_memory/audit.py": (
                "from cortex_core.log_fields import RECALL_LOGGER\n"
                "_logger = logging.getLogger(RECALL_LOGGER)\n"
            )
        },
    )
    with pytest.raises(logcalls.LogCallError, match="RECALL_LOGGER, which its own top level"):
        loggernames.loggers(tmp_path)


def test_a_module_that_binds_its_logger_name_and_writes_it_again_is_a_fault(
    tmp_path: Path,
) -> None:
    """The declaration is what the constant registry ties the restating documents to, so a sink
    holding both spellings can move the literal alone and leave them on an abandoned name. The
    fault names the binding, that being the spelling the call is asked to pass."""
    brain(
        tmp_path,
        {
            "tools/src/cortex_tools/audit.py": (
                '_LOGGER_NAME = "cortex.tools.audit"\n'
                '_logger = logging.getLogger("cortex.tools.audit")\n'
            )
        },
    )
    with pytest.raises(logcalls.LogCallError, match="binds it above as _LOGGER_NAME; pass"):
        loggernames.loggers(tmp_path)


def test_every_binding_of_a_twice_spelled_logger_name_is_named(tmp_path: Path) -> None:
    """A module that bound the name twice would otherwise be told to pass one of two, with the
    reader picking whichever the dict happened to hold first."""
    brain(
        tmp_path,
        {
            "tools/src/cortex_tools/audit.py": (
                '_TRAIL = "cortex.tools.audit"\n'
                '_LOGGER_NAME = "cortex.tools.audit"\n'
                '_logger = logging.getLogger("cortex.tools.audit")\n'
            )
        },
    )
    with pytest.raises(logcalls.LogCallError, match="as _LOGGER_NAME, _TRAIL;"):
        loggernames.loggers(tmp_path)


def test_a_literal_beside_a_binding_of_some_other_string_is_left_alone(tmp_path: Path) -> None:
    """The rule is one name written once, not a ban on declaring anything beside a literal call."""
    brain(
        tmp_path,
        {
            "tools/src/cortex_tools/audit.py": (
                '_TIER = "cortex.tools.tier"\ngetLogger("cortex.tools.audit")\n'
            )
        },
    )
    assert set(loggernames.loggers(tmp_path)) == {"cortex.tools.audit"}


def test_a_package_barrel_claims_the_package_name_and_not_its_init(tmp_path: Path) -> None:
    brain(tmp_path, {"core/src/cortex_core/__init__.py": "getLogger(__name__)\n"})
    assert set(loggernames.loggers(tmp_path)) == {"cortex_core"}


def test_a_pruned_directory_inside_the_source_tree_is_not_walked(tmp_path: Path) -> None:
    """A cached copy of a module would otherwise claim the same name as the module itself."""
    settler(tmp_path)
    brain(tmp_path, {"core/src/cortex_core/__pycache__/stale.py": "getLogger(__name__)\n"})
    assert set(loggernames.loggers(tmp_path)) == {"cortex_core.swap_settle"}


def test_a_package_with_no_source_tree_is_passed_over(tmp_path: Path) -> None:
    settler(tmp_path)
    (tmp_path / "brain" / "packages" / "notes").mkdir()
    assert set(loggernames.loggers(tmp_path)) == {"cortex_core.swap_settle"}


def test_two_files_claiming_one_logger_name_is_a_fault_not_a_coin_toss(tmp_path: Path) -> None:
    brain(
        tmp_path,
        {
            "tools/src/cortex_tools/audit.py": 'getLogger("cortex.tools.audit")\n',
            "memory/src/cortex_memory/audit.py": 'getLogger("cortex.tools.audit")\n',
        },
    )
    with pytest.raises(logcalls.LogCallError, match="both declare the logger"):
        loggernames.loggers(tmp_path)


def test_a_brain_that_cannot_be_walked_is_a_fault(tmp_path: Path) -> None:
    with pytest.raises(logcalls.LogCallError, match="cannot read brain/packages"):
        loggernames.loggers(tmp_path)


def test_a_source_file_that_is_not_text_is_a_fault(tmp_path: Path) -> None:
    settler(tmp_path)
    (tmp_path / "brain/packages/core/src/cortex_core/blob.py").write_bytes(b"\xff\xfe\x00")
    with pytest.raises(logcalls.LogCallError, match=r"cannot read .*blob\.py"):
        loggernames.loggers(tmp_path)


# ── the brain this reader is written for ───────────────────────────────────────


def declarations(root: Path) -> dict[str, str]:
    """Every logger name a brain module binds under ``DECLARATION``, against the file binding it.

    A second walk of the tree ``loggers`` already walks, deliberately: the guard below compares
    the two answers, so a walk here that stopped finding modules comes back empty against a set
    that is not, rather than agreeing with itself about a tree neither of them read.
    """
    found: dict[str, str] = {}
    for package in sorted((root / logcalls.BRAIN_PACKAGES).iterdir()):
        source = package / logcalls.SOURCE_DIR
        if not source.is_dir():
            continue
        for module in sorted(source.rglob("*.py")):
            if SKIPPED_DIRS & set(module.relative_to(source).parts):
                continue
            shown = module.relative_to(root).as_posix()
            strings, _ = constants(parse(module, shown))
            if (name := strings.get(DECLARATION)) is not None:
                found[name] = shown
    return found


def self_named(root: Path) -> dict[str, str]:
    """Every logger the brain writes through under a name that is not its module's own.

    Read off the call rather than off any declaration: ``loggers`` answers with the name the CALL
    carries, whichever of the three spellings it carries it in, so a name that is not the dotted
    path of the module writing it is a sink that chose its own, however it chose it.
    """
    found: dict[str, str] = {}
    for name, shown in loggernames.loggers(root).items():
        inside = shown.split(f"/{logcalls.SOURCE_DIR}/", 1)[1]
        if name != loggernames.dotted(Path(inside)):
            found[name] = shown
    return found


def test_every_self_named_sink_binds_the_name_its_own_call_is_handed() -> None:
    """The one place a sink's declaration meets the call handed it, over whatever the tree holds.

    Every module but a couple names its logger ``__name__``. A sink that names itself does so
    because its lines are read as a trail, which is why documents restate that name, which is why
    the name is a declaration for the constant registry to tie them to. Neither half of that says
    the sink passes what it declares: ``getLogger(_LOGGER_NAME)`` carries an identifier, so a
    module binding one name and passing another is two names rather than one spelled twice, which
    is the shape the one-name rule sees and lets through (ADR-0009 declared-name addendum).

    Comparing the two readings as SETS is what holds every direction of that at once, and holds
    them for a sink written tomorrow rather than for the two written down. A sink that passes
    another name is a self-named logger this brain declares nowhere; one that declares a name it
    stops passing is a declaration the documents are still tied to and nothing writes; one that
    names itself with a bare literal has no declaration to tie them to at all; and one that binds
    its name under some other identifier is outside the naming the left-hand set is read by, which
    is the shape a derived rule has to hold rather than assume (ADR-0029 addendum on the naming a
    derived set is read out of). Each is one set carrying a pair the other does not.

    The non-emptiness beside it is what keeps the comparison from passing on two empty answers,
    and it is also the guard on the fixtures above: a brain where no sink named itself would make
    both of the spellings they exercise fiction.
    """
    sinks = self_named(REPO_ROOT)
    assert sinks, "no sink in this brain names its own logger, so the fixtures above are fiction"
    assert declarations(REPO_ROOT) == sinks, (
        f"a sink that names its own logger binds that name as {DECLARATION} and hands the binding "
        f"to its own getLogger call; on the left is what the brain declares that way and on the "
        f"right what its calls really pass"
    )
