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

# A projector loaded beside a model, which is the second of llama.cpp's file flags this reader
# takes: a compose service spending one names two artifacts.
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


def test_the_variable_after_the_projector_flag_is_an_artifact_that_argv_names_too() -> None:
    """A projector is weights under the same mount loaded by the same engine, and llama.cpp names
    it with its own flag, so the item after `--mmproj` is read exactly as the one after `--model`
    and a service spending a projector variable is held to the family like any other."""
    assert spends(_one(SIGHTED)) == (
        "CORTEX_MODEL_FILE_SUBAGENT",
        "CORTEX_MODEL_FILE_SUBAGENT_MMPROJ",
    )


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


# ── what the sidecar resolves under the mount ──────────────────────────────────

# Three artifacts under three field names, none of which this reader is told: one a tier reads
# its `model_path` from, one handed by keyword, and one resolved into a local that a flag then
# spends, which is the projector's own shape. The names are deliberately outside the `_file`
# spelling the committed sidecar happens to use, since a name is what an author picks and a
# resolution is what the module does. The resolver is kept apart so a test can take it away.
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


def _line(text: str, needle: str) -> int:
    """The one-based line of ``text`` carrying ``needle``, asserted to be exactly one line."""
    lines = [number for number, line in enumerate(text.splitlines(), 1) if needle in line]
    assert len(lines) == 1, (needle, lines)
    return lines[0]


def test_a_field_the_sidecar_resolves_is_an_artifact_whatever_it_is_named_and_wherever_spent() -> (
    None
):
    """The domain is what the module hands to its resolver. `cortex_mmproj_path` is the projector
    under a name the old suffix reading would have missed, resolved into a local that `--mmproj`
    then spends; `brain_weights` is handed by keyword; each is reported where it is resolved."""
    at_tier = _line(SETTINGS, "self._path(self.cortex_file)")
    by_keyword = _line(SETTINGS, "file=self.brain_weights")
    into_local = _line(SETTINGS, "self._path(self.cortex_mmproj_path)")
    assert resolved(ast.parse(SETTINGS)) == (
        ("cortex_file", "CORTEX_MODEL_FILE_CORTEX", at_tier),
        ("brain_weights", "CORTEX_MODEL_FILE_BRAIN", by_keyword),
        ("cortex_mmproj_path", "CORTEX_MODEL_FILE_CORTEX_MMPROJ", into_local),
    )


def test_a_field_never_resolved_and_one_resolved_in_another_class_are_both_passed_over() -> None:
    """Four shapes are passed over, each of which would be a fault of its own if it were read: a
    setting that is no artifact (`cortex_ngl`, handed to a tier but never resolved), two paths
    that are no artifact (`llama_bin` and the mount root itself, which name no variable), and a
    field resolved in some other class, which is not this sidecar's declaration."""
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
    """A second place reading the mount is a second resolver this reader does not read, and an
    artifact joined there would be missed in silence, so the shape is reported with its remedy."""
    by_hand = SETTINGS.replace(
        "self._path(file=self.brain_weights)", 'f"{self.models_root}/{self.brain_weights}"'
    )
    with pytest.raises(HostedTierError, match="reads models_root in tiers rather than in _path"):
        resolved(ast.parse(by_hand))


def test_a_settings_class_handing_no_field_to_the_resolver_is_refused() -> None:
    """The fixture shape every sidecar test in this suite writes, with its calls renamed: no
    method reads the mount, so the refusal above stays quiet, and the floor is what reports a
    reader that would otherwise go on finding every tier's artifact while the projector dropped."""
    renamed = SETTINGS.replace("self._path(", "self._under(").replace(RESOLVER_METHOD, "")
    assert "models_root.rstrip" not in renamed
    with pytest.raises(HostedTierError, match="hands no ModelHostConfig field to _path"):
        resolved(ast.parse(renamed))


# ── the same reader, against the tree it is written for ────────────────────────


def test_the_committed_sidecar_names_every_tiers_artifact_and_not_only_the_subagents() -> None:
    """This is the half the membership reader filters away. The sidecar's three tiers name three
    artifacts, and the two that serve no subagent are held to the naming convention exactly as the
    one that does. The projector is the fourth, found by the resolver it is handed to rather than
    by a tier's `model_path`."""
    found = {artifact.where: artifact.variable for artifact in tiered(REPO_ROOT)}
    assert found == {
        "cortex_file": "CORTEX_MODEL_FILE_CORTEX",
        "brain_file": "CORTEX_MODEL_FILE_BRAIN",
        "subagent_gpu_file": "CORTEX_MODEL_FILE_SUBAGENT_GPU",
        "cortex_mmproj_file": "CORTEX_MODEL_FILE_CORTEX_MMPROJ",
    }


def test_an_artifact_a_tier_spends_is_reported_once_and_at_the_tier_that_spends_it() -> None:
    """Both readings find `cortex_file`, and it is reported once: a reader is sent to the tier's
    line, and the resolver walk adds only what no tier's `model_path` named, at the line the
    sidecar resolves it on."""
    walked = tiered(REPO_ROOT)
    found = [artifact for artifact in walked if artifact.where == "cortex_file"]
    projector = [artifact for artifact in walked if artifact.where == "cortex_mmproj_file"]
    assert len(found) == 1, found
    assert len(projector) == 1, projector
    source = (REPO_ROOT / found[0].file).read_text(encoding="utf-8").splitlines()
    assert "self._path(self.cortex_mmproj_file)" in source[projector[0].line - 1]
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
