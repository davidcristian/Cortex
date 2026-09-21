from pathlib import Path

import pytest

import logcalls
import loggernames
from moduleconstants import constants, parse
from skippeddirs import SKIPPED_DIRS

REPO_ROOT = Path(__file__).resolve().parents[2]

DECLARATION = "_LOGGER_NAME"

SETTLE = (
    '"""A miniature of the settler."""\n\nimport logging\n\n_logger = logging.getLogger(__name__)\n'
)


def brain(root: Path, files: dict[str, str]) -> None:
    """Write a small brain tree, each path relative to `brain/packages/`."""
    for relative, text in files.items():
        path = root / "brain" / "packages" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def settler(root: Path) -> None:
    """Write the one package every test about the directory walk starts from."""
    brain(root, {"core/src/cortex_core/swap_settle.py": SETTLE})


def test_a_module_logging_under_name_is_found_by_its_dotted_path(tmp_path: Path) -> None:
    settler(tmp_path)
    assert loggernames.loggers(tmp_path) == {
        "cortex_core.swap_settle": "brain/packages/core/src/cortex_core/swap_settle.py"
    }


def test_a_sink_that_names_itself_is_found_under_the_name_it_chose(tmp_path: Path) -> None:
    brain(tmp_path, {"tools/src/cortex_tools/audit.py": 'getLogger("cortex.tools.audit")\n'})
    assert set(loggernames.loggers(tmp_path)) == {"cortex.tools.audit"}


def test_a_sink_naming_its_logger_through_a_constant_is_found_under_that_name(
    tmp_path: Path,
) -> None:
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


def test_every_binding_of_a_twice_written_logger_name_is_named(tmp_path: Path) -> None:
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


def declarations(root: Path) -> dict[str, str]:
    """Return every logger name a brain module binds under ``DECLARATION``, by file."""
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
    """Return every logger the brain writes through under a name other than its module's own."""
    found: dict[str, str] = {}
    for name, shown in loggernames.loggers(root).items():
        inside = shown.split(f"/{logcalls.SOURCE_DIR}/", 1)[1]
        if name != loggernames.dotted(Path(inside)):
            found[name] = shown
    return found


def test_every_self_named_sink_binds_the_name_its_own_call_is_handed() -> None:
    sinks = self_named(REPO_ROOT)
    assert sinks, "no sink in this brain names its own logger, so the fixtures above are fiction"
    assert declarations(REPO_ROOT) == sinks, (
        f"a sink that names its own logger binds that name as {DECLARATION} and hands the binding "
        f"to its own getLogger call; on the left is what the brain declares that way and on the "
        f"right what its calls really pass"
    )
