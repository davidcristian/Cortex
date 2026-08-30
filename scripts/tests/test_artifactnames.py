"""Behaviour of the reader that finds every model artifact this tree names.

The question here is narrower than the one `subagentservers.py` answers and sits underneath it:
not which servers serve subagents, which is decided from the variable an artifact is named under,
but which variables name an artifact at all, so that the deciding can be held to a spelling. The
domain is therefore structural in both languages, and the tests below are mostly about what counts
as naming an artifact and what deliberately does not.

The last tests read the committed tree, because a reader agreeing with its own fixtures and
finding nothing real would leave the rule above it green over an empty set.
"""

from pathlib import Path

import pytest

from artifactnames import composed, named, spends, tiered
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
    """A compose tree written under ``root``, which is how a stack arrives here."""
    (root / "docker").mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / "docker" / name).write_text(text, encoding="utf-8")
    return root


def _one(text: str) -> Started:
    """The one service of ``text`` that starts with a command, which is the argv under test."""
    found = [started for started in read_starts(text) if started.command is not None]
    assert len(found) == 1, found
    return found[0]


# ── what an argv names an artifact under ───────────────────────────────────────


def test_the_variable_after_the_model_flag_is_the_artifact_that_argv_names() -> None:
    assert spends(_one(SUBAGENT)) == ("CORTEX_MODEL_FILE_SUBAGENT",)


def test_a_model_path_written_out_in_full_names_no_variable_to_hold() -> None:
    """There is no name to misspell in a literal path, and the wiring is what finds such a
    server; a reader reporting the path itself would be reporting a value, not a name."""
    assert spends(_one(WRITTEN_OUT)) == ()


def test_a_model_flag_written_last_is_followed_by_nothing_rather_than_by_an_artifact() -> None:
    """An argv ending on the flag names no file at all, which is a stack that fails at startup
    rather than a name this rule has anything to say about."""
    ends_on_it = 'services:\n  s:\n    command:\n      - "--model"\n'
    assert spends(_one(ends_on_it)) == ()


def test_a_service_declaring_no_command_names_nothing(tmp_path: Path) -> None:
    """The normal shape for an override re-opening `brain:`, and the shape the model host has:
    its argv comes from a supervisor, and the sidecar's own declaration is read instead."""
    reopened = 'services:\n  brain:\n    environment:\n      CORTEX_X: "1"\n'
    assert composed(_tree(tmp_path, {"docker-compose.body.yml": reopened})) == ()


def test_the_short_spelling_of_the_model_flag_is_not_read() -> None:
    """Deliberate, and the fixture is this tree's own shape: an MCP sidecar started with
    `python -m <module>`. Reading `-m` would call the module an artifact and redden a correct
    service whose only remedy would be to teach the gate."""
    assert spends(_one(PYTHON_MODULE)) == ()


def test_an_argv_that_declares_itself_an_embedding_server_names_an_artifact_like_any_other(
    tmp_path: Path,
) -> None:
    """What a server serves is the membership reader's question and not this one, so the CPU
    embedder's own artifact is enumerated beside the subagent's and held to the same spelling.
    The exclusion that used to sit here excused the one artifact in this tree named outside the
    family, in the block a new non-chat model server would be copied from."""
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
    """The substitution reader owns that refusal and this one re-raises it with the service on
    it, exactly as the membership reader does with the same reading."""
    broken = 'services:\n  s:\n    command:\n      - "--model"\n      - "${"\n'
    with pytest.raises(ComposeStartError, match="the command of 's' cannot be read"):
        spends(_one(broken))


def test_a_compose_file_that_cannot_be_read_is_named(tmp_path: Path) -> None:
    _tree(tmp_path, {"docker-compose.yml": SUBAGENT})
    (tmp_path / "docker" / "docker-compose.yml").write_bytes(b"\xff\xfe not text")
    with pytest.raises(ComposeStartError, match="cannot read"):
        composed(tmp_path)


# ── the same reader, against the tree it is written for ────────────────────────


def test_the_committed_sidecar_names_every_tiers_artifact_and_not_only_the_subagents() -> None:
    """The half the membership reader filters away. Its three tiers name three artifacts, and the
    two that serve no subagent are held to the family exactly as the one that does."""
    found = {artifact.where: artifact.variable for artifact in tiered(REPO_ROOT)}
    assert found == {
        "cortex_file": "CORTEX_MODEL_FILE_CORTEX",
        "brain_file": "CORTEX_MODEL_FILE_BRAIN",
        "subagent_gpu_file": "CORTEX_MODEL_FILE_SUBAGENT_GPU",
    }


def test_the_committed_tree_names_the_artifacts_it_ships_in_both_languages() -> None:
    """Both halves at once, since the rule above runs over the join. Every artifact this tree
    names is here, the CPU embedder's included: nothing is excluded from this reading any more,
    which is what makes the family the rule holds them to a family rather than a convention with
    one documented exception."""
    found = {artifact.variable for artifact in named(REPO_ROOT)}
    assert found == {
        "CORTEX_MODEL_FILE_EMBED",
        "CORTEX_MODEL_FILE_SUBAGENT",
        "CORTEX_MODEL_FILE_SUBAGENT_QWEN",
        "CORTEX_MODEL_FILE_CORTEX",
        "CORTEX_MODEL_FILE_BRAIN",
        "CORTEX_MODEL_FILE_SUBAGENT_GPU",
    }
