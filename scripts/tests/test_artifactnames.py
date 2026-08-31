"""Tests for the reader that finds every model artifact this tree names.

The question here sits underneath the one `subagentservers.py` answers. That reader determines
which servers serve subagents, from the variable an artifact is named under; this one determines
which variables name an artifact at all, so that the answer can be held to a spelling. The domain
is structural in both languages, and the tests below are mostly about what counts as naming an
artifact and what deliberately does not.

The last tests read the committed tree, because a reader agreeing with its own fixtures and
finding nothing in the tree would leave the rule above it green over an empty set.
"""

import ast
from pathlib import Path

import pytest

from artifactnames import composed, files, named, spends, tiered
from composestarts import ComposeStartError, Started, read_starts

REPO_ROOT = Path(__file__).resolve().parents[2]

SUBAGENT = """\
services:
  llama-subagent:
    image: "ghcr.io/ggml-org/llama.cpp:server"
    command:
      - "--model"
      - "/models/${CORTEX_MODEL_FILE_SUBAGENT:-vendor/small.gguf}"
      - "--jinja"
"""

WRITTEN_OUT = """\
services:
  llama-subagent:
    command:
      - "--model"
      - "/models/written-out.gguf"
"""

EMBEDDER = """\
services:
  llama-embed:
    image: "ghcr.io/ggml-org/llama.cpp:server"
    command:
      - "--model"
      - "/models/${CORTEX_MODEL_FILE_EMBED:-nomic/nomic-embed.gguf}"
      - "--embeddings"
"""

# The reason the short spelling of the model flag is not read: this tree really starts a sidecar
# this way, and a reader taking the item after every `-m` would call a module name an artifact.
PYTHON_MODULE = """\
services:
  mcp-email:
    command:
      - "python"
      - "-m"
      - "${CORTEX_EMAIL_MODULE:-cortex_email}"
"""


def _tree(root: Path, files: dict[str, str]) -> Path:
    """Write a compose tree under ``root``, which is the shape a stack arrives in."""
    (root / "docker").mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / "docker" / name).write_text(text, encoding="utf-8")
    return root


def _one(text: str) -> Started:
    """Return the one service of ``text`` that declares a command, the argv under test."""
    found = [started for started in read_starts(text) if started.command is not None]
    assert len(found) == 1, found
    return found[0]


# ── what an argv names an artifact under ───────────────────────────────────────


def test_the_variable_after_the_model_flag_is_the_artifact_that_argv_names() -> None:
    assert spends(_one(SUBAGENT)) == ("CORTEX_MODEL_FILE_SUBAGENT",)


def test_a_model_path_written_out_in_full_names_no_variable_to_hold() -> None:
    """A literal path carries no variable name to hold to the convention, and the wiring is what
    finds such a server. Reporting the path itself would report a value rather than a name."""
    assert spends(_one(WRITTEN_OUT)) == ()


def test_a_model_flag_written_last_is_followed_by_nothing_rather_than_by_an_artifact() -> None:
    """An argv ending on the flag names no file at all, which is a stack that fails at startup
    rather than a name this rule has anything to say about."""
    ends_on_it = 'services:\n  s:\n    command:\n      - "--model"\n'
    assert spends(_one(ends_on_it)) == ()


def test_a_service_declaring_no_command_names_nothing(tmp_path: Path) -> None:
    """This is the normal shape for an override re-opening `brain:`, and the shape the model host
    has: its argv comes from a supervisor, so the sidecar's own declaration is read instead."""
    reopened = 'services:\n  brain:\n    environment:\n      CORTEX_X: "1"\n'
    assert composed(_tree(tmp_path, {"docker-compose.body.yml": reopened})) == ()


def test_the_short_spelling_of_the_model_flag_is_not_read() -> None:
    """The short `-m` is skipped deliberately. The fixture is this tree's own shape, an MCP sidecar
    started with `python -m <module>`, and reading `-m` would call the module an artifact and fail
    a correct service whose only remedy would be to teach the gate."""
    assert spends(_one(PYTHON_MODULE)) == ()


def test_an_argv_that_declares_itself_an_embedding_server_names_an_artifact_like_any_other(
    tmp_path: Path,
) -> None:
    """What a server serves is the membership reader's question rather than this one, so the CPU
    embedder's own artifact is enumerated beside the subagent's and held to the same spelling.
    The exclusion that used to sit here excused the one artifact in this tree named outside the
    convention, in the block a new non-chat model server would be copied from."""
    stack = {
        "docker-compose.memory.yml": EMBEDDER,
        "docker-compose.subagents.yml": SUBAGENT,
    }
    found = composed(_tree(tmp_path, stack))
    assert [artifact.variable for artifact in found] == [
        "CORTEX_MODEL_FILE_EMBED",
        "CORTEX_MODEL_FILE_SUBAGENT",
    ]


def test_an_artifact_carries_the_file_the_service_and_the_line_it_is_named_on(
    tmp_path: Path,
) -> None:
    """A fault has to send a reader to the line, so all three travel with the name."""
    found = composed(_tree(tmp_path, {"docker-compose.subagents.yml": SUBAGENT}))
    assert len(found) == 1, found
    assert found[0].file == "docker/docker-compose.subagents.yml"
    assert found[0].where == "llama-subagent"
    assert found[0].line == 2


# ── and what it refuses rather than guesses at ─────────────────────────────────


def test_a_command_spending_a_dollar_form_no_reader_can_name_is_raised() -> None:
    """The substitution reader raises, and this reader re-raises with the service named, exactly as
    the membership reader does with the same reading."""
    broken = 'services:\n  s:\n    command:\n      - "--model"\n      - "${"\n'
    with pytest.raises(ComposeStartError, match="the command of 's' cannot be read"):
        spends(_one(broken))


def test_a_compose_file_that_cannot_be_read_is_named(tmp_path: Path) -> None:
    _tree(tmp_path, {"docker-compose.yml": SUBAGENT})
    (tmp_path / "docker" / "docker-compose.yml").write_bytes(b"\xff\xfe not text")
    with pytest.raises(ComposeStartError, match="cannot read"):
        composed(tmp_path)


# ── what a settings field's own name says it holds ─────────────────────────────

SETTINGS = '''\
class Elsewhere:
    """A field of the same name outside the settings class names nothing here."""

    stray_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_STRAY")


class ModelHostConfig(BaseSettings):
    """A class docstring binds nothing."""

    llama_bin: str = "/app/llama-server"
    cortex_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_CORTEX")
    cortex_mmproj_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_CORTEX_MMPROJ")
    cortex_ngl: int = Field(default=99, validation_alias="CORTEX_NGL")

    def tiers(self) -> tuple[str, ...]:
        return ()
'''


def test_a_settings_field_naming_a_file_is_an_artifact_whichever_keyword_spends_it() -> None:
    """This is the projector's shape: it reaches an argv through a tier's `extra` rather than
    through its `model_path`, so the field's own name is what says it holds a file."""
    assert files(ast.parse(SETTINGS)) == (
        ("cortex_file", "CORTEX_MODEL_FILE_CORTEX", 11),
        ("cortex_mmproj_file", "CORTEX_MODEL_FILE_CORTEX_MMPROJ", 12),
    )


def test_a_field_that_names_no_file_and_one_outside_the_settings_class_are_both_passed_over() -> (
    None
):
    """Three shapes are passed over, each of which would be a fault of its own if it were read: a
    setting that is no artifact (`cortex_ngl`), a path that is no artifact (`llama_bin`, which
    names no variable), and a field of the right shape in some other class, which is not this
    sidecar's declaration."""
    found = [field for field, _, _ in files(ast.parse(SETTINGS))]
    assert "cortex_ngl" not in found
    assert "llama_bin" not in found
    assert "stray_file" not in found


# ── the same reader, against the tree it is written for ────────────────────────


def test_the_committed_sidecar_names_every_tiers_artifact_and_not_only_the_subagents() -> None:
    """This is the half the membership reader filters away. The sidecar's three tiers name three
    artifacts, and the two that serve no subagent are held to the naming convention exactly as the
    one that does. The projector is the fourth, found by its field rather than by a tier's
    `model_path`."""
    found = {artifact.where: artifact.variable for artifact in tiered(REPO_ROOT)}
    assert found == {
        "cortex_file": "CORTEX_MODEL_FILE_CORTEX",
        "brain_file": "CORTEX_MODEL_FILE_BRAIN",
        "subagent_gpu_file": "CORTEX_MODEL_FILE_SUBAGENT_GPU",
        "cortex_mmproj_file": "CORTEX_MODEL_FILE_CORTEX_MMPROJ",
    }


def test_an_artifact_a_tier_spends_is_reported_once_and_at_the_tier_that_spends_it() -> None:
    """Both readings find `cortex_file`, and it is reported once: a reader is sent to the tier's
    line, and the field walk adds only what no tier's `model_path` named."""
    walked = tiered(REPO_ROOT)
    found = [artifact for artifact in walked if artifact.where == "cortex_file"]
    projector = [artifact for artifact in walked if artifact.where == "cortex_mmproj_file"]
    assert len(found) == 1, found
    assert len(projector) == 1, projector
    source = (REPO_ROOT / found[0].file).read_text(encoding="utf-8").splitlines()
    assert "cortex_mmproj_file" in source[projector[0].line - 1]
    assert "TierArgs(" in source[found[0].line - 1]


def test_the_committed_tree_names_the_artifacts_it_ships_in_both_languages() -> None:
    """Both halves at once, since the rule above runs over the join. Every artifact this tree names
    is here, the CPU embedder's included, so nothing is excluded from this reading and the naming
    convention the rule holds them to has no documented exception."""
    found = {artifact.variable for artifact in named(REPO_ROOT)}
    assert found == {
        "CORTEX_MODEL_FILE_EMBED",
        "CORTEX_MODEL_FILE_SUBAGENT",
        "CORTEX_MODEL_FILE_SUBAGENT_QWEN",
        "CORTEX_MODEL_FILE_CORTEX",
        "CORTEX_MODEL_FILE_CORTEX_MMPROJ",
        "CORTEX_MODEL_FILE_BRAIN",
        "CORTEX_MODEL_FILE_SUBAGENT_GPU",
    }
