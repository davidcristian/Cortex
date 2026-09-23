import ast
from pathlib import Path

import pytest

from artifactnames import composed, named, resolved, spends, tiered
from composestarts import ComposeStartError, Started, read_starts
from hostedtiers import HostedTierError

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

SIGHTED = """\
services:
  llama-subagent:
    command:
      - "--model"
      - "/models/${CORTEX_MODEL_FILE_SUBAGENT:-vendor/small.gguf}"
      - "--mmproj"
      - "/models/${CORTEX_MODEL_FILE_SUBAGENT_MMPROJ:-vendor/mmproj.gguf}"
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

PYTHON_MODULE = """\
services:
  mcp-email:
    command:
      - "python"
      - "-m"
      - "${CORTEX_EMAIL_MODULE:-cortex_email}"
"""


def _tree(root: Path, files: dict[str, str]) -> Path:
    """Write the named compose files into ``root``/docker."""
    (root / "docker").mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / "docker" / name).write_text(text, encoding="utf-8")
    return root


def _one(text: str) -> Started:
    """Return the one service of ``text`` that declares a command, the argv under test."""
    found = [started for started in read_starts(text) if started.command is not None]
    assert len(found) == 1, found
    return found[0]


def test_the_variable_after_the_model_flag_is_the_artifact_that_argv_names() -> None:
    assert spends(_one(SUBAGENT)) == ("CORTEX_MODEL_FILE_SUBAGENT",)


def test_the_variable_after_the_projector_flag_is_an_artifact_that_argv_names_too() -> None:
    assert spends(_one(SIGHTED)) == (
        "CORTEX_MODEL_FILE_SUBAGENT",
        "CORTEX_MODEL_FILE_SUBAGENT_MMPROJ",
    )


def test_a_model_path_written_out_in_full_names_no_variable_to_hold() -> None:
    assert spends(_one(WRITTEN_OUT)) == ()


def test_a_model_flag_written_last_is_followed_by_nothing_rather_than_by_an_artifact() -> None:
    ends_on_it = 'services:\n  s:\n    command:\n      - "--model"\n'
    assert spends(_one(ends_on_it)) == ()


def test_a_service_declaring_no_command_names_nothing(tmp_path: Path) -> None:
    reopened = 'services:\n  brain:\n    environment:\n      CORTEX_X: "1"\n'
    assert composed(_tree(tmp_path, {"docker-compose.body.yml": reopened})) == ()


def test_the_short_form_of_the_model_flag_is_not_read() -> None:
    assert spends(_one(PYTHON_MODULE)) == ()


def test_an_argv_that_declares_itself_an_embedding_server_names_an_artifact_like_any_other(
    tmp_path: Path,
) -> None:
    stack = {
        "docker-compose.memory.yml": EMBEDDER,
        "docker-compose.subagents.yml": SUBAGENT,
    }
    found = composed(_tree(tmp_path, stack))
    assert [artifact.variable for artifact in found] == [
        "CORTEX_MODEL_FILE_EMBED",
        "CORTEX_MODEL_FILE_SUBAGENT",
    ]


def test_an_artifact_records_the_file_the_service_and_the_line_it_is_named_on(
    tmp_path: Path,
) -> None:
    found = composed(_tree(tmp_path, {"docker-compose.subagents.yml": SUBAGENT}))
    assert len(found) == 1, found
    assert found[0].file == "docker/docker-compose.subagents.yml"
    assert found[0].where == "llama-subagent"
    assert found[0].line == 2


def test_a_command_spending_a_dollar_form_no_reader_can_name_is_raised() -> None:
    broken = 'services:\n  s:\n    command:\n      - "--model"\n      - "${"\n'
    with pytest.raises(ComposeStartError, match="the command of 's' cannot be read"):
        spends(_one(broken))


def test_a_compose_file_that_cannot_be_read_is_named(tmp_path: Path) -> None:
    _tree(tmp_path, {"docker-compose.yml": SUBAGENT})
    (tmp_path / "docker" / "docker-compose.yml").write_bytes(b"\xff\xfe not text")
    with pytest.raises(ComposeStartError, match="cannot read"):
        composed(tmp_path)


DECLARED = '''\
class Elsewhere:
    """A field resolved in some other class names nothing here."""

    stray_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_STRAY")

    def tiers(self):
        return (self._path(self.stray_file),)


class ModelHostConfig(BaseSettings):
    """A class docstring binds nothing."""

    llama_bin: str = "/app/llama-server"
    models_root: str = "/models"
    cortex_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_CORTEX")
    cortex_mmproj_path: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_CORTEX_MMPROJ")
    brain_weights: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_BRAIN")
    cortex_ngl: int = Field(default=99, validation_alias="CORTEX_NGL")

    def tiers(self):
        return (
            TierArgs(model_path=self._path(self.cortex_file), ngl=self.cortex_ngl),
            TierArgs(model_path=self._path(file=self.brain_weights), extra=self._vision()),
        )

    def roster(self):
        return tuple(tier.model_path for tier in self.tiers())

    def _vision(self):
        path = self._path(self.cortex_mmproj_path)
        return ("--mmproj", path) if path else ()

'''

RESOLVER_METHOD = """\
    def _path(self, file):
        return f"{self.models_root.rstrip('/')}/{file}" if file else ""
"""

SETTINGS = DECLARED + RESOLVER_METHOD


def _line(text: str, search_text: str) -> int:
    """Return the one-based line of ``text`` containing ``search_text``, asserting there is one."""
    lines = [number for number, line in enumerate(text.splitlines(), 1) if search_text in line]
    assert len(lines) == 1, (search_text, lines)
    return lines[0]


def test_a_field_the_sidecar_resolves_is_an_artifact_whatever_it_is_named_and_wherever_spent() -> (
    None
):
    at_tier = _line(SETTINGS, "self._path(self.cortex_file)")
    by_keyword = _line(SETTINGS, "file=self.brain_weights")
    into_local = _line(SETTINGS, "self._path(self.cortex_mmproj_path)")
    assert resolved(ast.parse(SETTINGS)) == (
        ("cortex_file", "CORTEX_MODEL_FILE_CORTEX", at_tier),
        ("brain_weights", "CORTEX_MODEL_FILE_BRAIN", by_keyword),
        ("cortex_mmproj_path", "CORTEX_MODEL_FILE_CORTEX_MMPROJ", into_local),
    )


def test_a_field_never_resolved_and_one_resolved_in_another_class_are_both_passed_over() -> None:
    found = [field for field, _, _ in resolved(ast.parse(SETTINGS))]
    assert "cortex_ngl" not in found
    assert "llama_bin" not in found
    assert "models_root" not in found
    assert "stray_file" not in found


def test_a_field_resolved_twice_is_one_artifact_reported_where_it_is_first_resolved() -> None:
    again = "    def again(self):\n        return self._path(self.cortex_file)\n\n"
    twice = SETTINGS.replace("    def roster(self):\n", again + "    def roster(self):\n")
    found = [(field, line) for field, _, line in resolved(ast.parse(twice))]
    assert found.count(("cortex_file", _line(SETTINGS, "self._path(self.cortex_file)"))) == 1
    assert [field for field, _ in found].count("cortex_file") == 1


def test_a_path_joined_onto_the_mount_outside_the_resolver_is_refused_by_name() -> None:
    by_hand = SETTINGS.replace(
        "self._path(file=self.brain_weights)", 'f"{self.models_root}/{self.brain_weights}"'
    )
    with pytest.raises(HostedTierError, match="reads models_root in tiers rather than in _path"):
        resolved(ast.parse(by_hand))


def test_a_settings_class_handing_no_field_to_the_resolver_is_refused() -> None:
    renamed = SETTINGS.replace("self._path(", "self._under(").replace(RESOLVER_METHOD, "")
    assert "models_root.rstrip" not in renamed
    with pytest.raises(HostedTierError, match="hands no ModelHostConfig field to _path"):
        resolved(ast.parse(renamed))


def test_the_committed_sidecar_names_every_tiers_artifact_and_not_only_the_subagents() -> None:
    found = {artifact.where: artifact.variable for artifact in tiered(REPO_ROOT)}
    assert found == {
        "cortex_file": "CORTEX_MODEL_FILE_CORTEX",
        "brain_file": "CORTEX_MODEL_FILE_BRAIN",
        "subagent_gpu_file": "CORTEX_MODEL_FILE_SUBAGENT_GPU",
        "brain_draft_file": "CORTEX_MODEL_FILE_BRAIN_DRAFT",
        "cortex_mmproj_file": "CORTEX_MODEL_FILE_CORTEX_MMPROJ",
    }


def test_an_artifact_a_tier_spends_is_reported_once_and_at_the_tier_that_spends_it() -> None:
    walked = tiered(REPO_ROOT)
    found = [artifact for artifact in walked if artifact.where == "cortex_file"]
    projector = [artifact for artifact in walked if artifact.where == "cortex_mmproj_file"]
    drafter = [artifact for artifact in walked if artifact.where == "brain_draft_file"]
    assert len(found) == 1, found
    assert len(projector) == 1, projector
    assert len(drafter) == 1, drafter
    source = (REPO_ROOT / found[0].file).read_text(encoding="utf-8").splitlines()
    assert "self._path(self.cortex_mmproj_file)" in source[projector[0].line - 1]
    assert "self._path(self.brain_draft_file)" in source[drafter[0].line - 1]
    assert "TierArgs(" in source[found[0].line - 1]


def test_the_committed_tree_names_the_artifacts_it_ships_in_both_languages() -> None:
    found = {artifact.variable for artifact in named(REPO_ROOT)}
    assert found == {
        "CORTEX_MODEL_FILE_EMBED",
        "CORTEX_MODEL_FILE_SUBAGENT",
        "CORTEX_MODEL_FILE_SUBAGENT_QWEN",
        "CORTEX_MODEL_FILE_CORTEX",
        "CORTEX_MODEL_FILE_CORTEX_MMPROJ",
        "CORTEX_MODEL_FILE_BRAIN",
        "CORTEX_MODEL_FILE_BRAIN_DRAFT",
        "CORTEX_MODEL_FILE_SUBAGENT_GPU",
    }
