from pathlib import Path

import pytest

from hostedtiers import (
    MODEL_MANAGER,
    UNREADABLE,
    HostedTierError,
    Tier,
    hosted,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

ARGV_MODULE = "tiers.py"
TIER_MODULE = "config.py"

ARGV = '''\
"""One tier's command line."""

_BIND_ALL = "0.0.0.0"
_JINJA = "--jinja"


def llama_server_argv(binary, tier):
    """The argv for one tier."""
    return (
        binary,
        "--host",
        _BIND_ALL,
        "--port",
        str(tier.port),
        _JINJA,
        *tier.extra,
        "--after",
    )
'''

CONFIG = '''\
"""The tiers a deployment may run."""

_NO_REASONING_BUDGET = "0"

_REASONING_OFF = (
    "--chat-template-kwargs",
    '{"enable_thinking": false}',
    "--reasoning-budget",
    _NO_REASONING_BUDGET,
)


class ModelHostConfig(BaseSettings):
    """Env-only settings."""

    bind_host: str = "0.0.0.0"
    cortex_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_CORTEX")
    subagent_gpu_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_SUBAGENT_GPU")

    def tiers(self):
        return (
            TierArgs(model_path=self._path(self.cortex_file), extra=()),
            TierArgs(model_path=self._path(self.subagent_gpu_file), extra=_REASONING_OFF),
        )
'''

BIND_ALL = "0.0.0.0"  # noqa: S104 -- asserted as a flag value, not bound by this process

REASONING_OFF = (
    "--chat-template-kwargs",
    '{"enable_thinking": false}',
    "--reasoning-budget",
    "0",
)

SUBAGENT_TAIL = (*REASONING_OFF, "--cache-ram", "0")


def _sidecar(root: Path, argv: str = ARGV, config: str = CONFIG) -> Path:
    """Write a model host service under ``root``."""
    (root / MODEL_MANAGER).mkdir(parents=True, exist_ok=True)
    (root / MODEL_MANAGER / ARGV_MODULE).write_text(argv, encoding="utf-8")
    (root / MODEL_MANAGER / TIER_MODULE).write_text(config, encoding="utf-8")
    return root


def _one(root: Path) -> Tier:
    found = hosted(root)
    assert len(found) == 1, found
    return found[0]


def test_the_tier_whose_artifact_setting_names_a_subagent_is_one(tmp_path: Path) -> None:
    tier = _one(_sidecar(tmp_path))
    assert tier.named == "CORTEX_MODEL_FILE_SUBAGENT_GPU"
    assert tier.file == (MODEL_MANAGER / TIER_MODULE).as_posix()


def test_a_tier_serving_anything_else_is_not_one(tmp_path: Path) -> None:
    assert [tier.named for tier in hosted(_sidecar(tmp_path))] == ["CORTEX_MODEL_FILE_SUBAGENT_GPU"]


def test_a_second_subagent_tier_is_found_the_day_it_is_declared(tmp_path: Path) -> None:
    config = CONFIG.replace(
        "    def tiers(self):",
        "    subagent_cpu_file: str = Field("
        'default="", validation_alias="CORTEX_MODEL_FILE_SUBAGENT_CPU")\n\n'
        "    def tiers(self):",
    ).replace(
        "        )\n",
        "            TierArgs(model_path=self._path(self.subagent_cpu_file)),\n        )\n",
    )
    found = hosted(_sidecar(tmp_path, config=config))
    assert [tier.named for tier in found] == [
        "CORTEX_MODEL_FILE_SUBAGENT_GPU",
        "CORTEX_MODEL_FILE_SUBAGENT_CPU",
    ]
    assert found[0].line < found[1].line, "declaration order, so a fault reads down the file"


def test_a_class_that_is_not_the_settings_class_declares_no_tiers(tmp_path: Path) -> None:
    config = CONFIG.replace(
        "class ModelHostConfig",
        'class Other:\n    other_file: str = Field(validation_alias="CORTEX_MODEL_FILE_SUBAGENT_X")'
        "\n\n\nclass ModelHostConfig",
    )
    assert _one(_sidecar(tmp_path, config=config)).named == "CORTEX_MODEL_FILE_SUBAGENT_GPU"


def test_a_field_naming_no_environment_variable_this_reader_can_resolve_is_no_tier(
    tmp_path: Path,
) -> None:
    config = CONFIG.replace(
        "    def tiers(self):",
        "    a_file: str = Field(default='')\n"
        "    b_file: str = Field(default='', validation_alias=SOME_NAME)\n"
        "    c_file: str = pydantic.Field(validation_alias='CORTEX_MODEL_FILE_SUBAGENT_C')\n\n"
        "    def tiers(self):",
    )
    assert _one(_sidecar(tmp_path, config=config)).named == "CORTEX_MODEL_FILE_SUBAGENT_GPU"


def test_the_tiers_own_tail_is_spliced_into_the_command_every_tier_shares(tmp_path: Path) -> None:
    assert _one(_sidecar(tmp_path)).command == (
        UNREADABLE,
        "--host",
        BIND_ALL,
        "--port",
        UNREADABLE,
        "--jinja",
        *REASONING_OFF,
        "--after",
    )


def test_an_item_only_the_running_program_knows_occupies_its_position(tmp_path: Path) -> None:
    command = _one(_sidecar(tmp_path)).command
    assert command[command.index("--port") + 1] == UNREADABLE


def test_a_tier_declaring_no_tail_has_only_what_every_tier_has(tmp_path: Path) -> None:
    config = CONFIG.replace(
        "self.subagent_gpu_file), extra=_REASONING_OFF", "self.subagent_gpu_file)"
    )
    assert _one(_sidecar(tmp_path, config=config)).command == (
        UNREADABLE,
        "--host",
        BIND_ALL,
        "--port",
        UNREADABLE,
        "--jinja",
        "--after",
    )


def test_a_sidecar_module_that_is_not_there_is_named(tmp_path: Path) -> None:
    _sidecar(tmp_path)
    (tmp_path / MODEL_MANAGER / ARGV_MODULE).unlink()
    with pytest.raises(HostedTierError, match=f"cannot read .*{ARGV_MODULE}"):
        hosted(tmp_path)


def test_a_tree_with_no_argv_builder_is_refused(tmp_path: Path) -> None:
    with pytest.raises(HostedTierError, match="declares no llama_server_argv"):
        hosted(_sidecar(tmp_path, argv="def other():\n    return ()\n"))


@pytest.mark.parametrize(
    "body",
    [
        "    return list(tier.extra)",
        "    if tier.ngl:\n        return (binary, *tier.extra)\n    return (binary,)",
        "    if tier.ngl:\n        return None\n    return (binary, *tier.extra)",
    ],
)
def test_an_argv_builder_this_reader_cannot_read_one_argv_out_of_is_refused(
    tmp_path: Path, body: str
) -> None:
    argv = f"def llama_server_argv(binary, tier):\n{body}\n"
    with pytest.raises(HostedTierError, match="does not return exactly one tuple"):
        hosted(_sidecar(tmp_path, argv=argv))


@pytest.mark.parametrize(
    "returned",
    [
        pytest.param("(binary, _JINJA)", id="no-tail-is-on-the-command-at-all"),
        pytest.param("(binary, *tier.extra, *tier.extra)", id="the-tail-is-written-twice"),
        pytest.param("(binary, *tier.extra, *other)", id="something-else-is-splatted-beside-it"),
    ],
)
def test_an_argv_builder_this_reader_cannot_place_a_tail_in_is_refused(
    tmp_path: Path, returned: str
) -> None:
    argv = f'_JINJA = "--jinja"\n\n\ndef llama_server_argv(binary, tier):\n    return {returned}\n'
    with pytest.raises(HostedTierError, match="does not splat"):
        hosted(_sidecar(tmp_path, argv=argv))


def test_a_settings_class_naming_no_environment_variable_is_refused(tmp_path: Path) -> None:
    config = (
        "class ModelHostConfig(BaseSettings):\n"
        "    def tiers(self):\n"
        "        return (TierArgs(model_path=self._path(self.cortex_file)),)\n"
    )
    with pytest.raises(HostedTierError, match="naming an environment variable"):
        hosted(_sidecar(tmp_path, config=config))


def test_a_tree_declaring_no_tier_at_all_is_refused(tmp_path: Path) -> None:
    config = (
        "class ModelHostConfig(BaseSettings):\n"
        '    cortex_file: str = Field(validation_alias="CORTEX_MODEL_FILE_CORTEX")\n'
    )
    with pytest.raises(HostedTierError, match="declares no TierArgs at all"):
        hosted(_sidecar(tmp_path, config=config))


def test_a_tier_whose_artifact_names_no_known_setting_is_refused(tmp_path: Path) -> None:
    config = CONFIG.replace("self._path(self.cortex_file)", '"/models/written-out.gguf"')
    with pytest.raises(HostedTierError, match="names no ModelHostConfig field"):
        hosted(_sidecar(tmp_path, config=config))


@pytest.mark.parametrize(
    "written",
    ["self._reasoning_off()", "(*_REASONING_OFF,)", '("--reasoning-budget", str(n))'],
)
def test_a_subagent_tiers_tail_this_reader_cannot_reduce_is_refused_by_name(
    tmp_path: Path, written: str
) -> None:
    config = CONFIG.replace("extra=_REASONING_OFF", f"extra={written}")
    with pytest.raises(HostedTierError, match="CORTEX_MODEL_FILE_SUBAGENT_GPU declares an extra"):
        hosted(_sidecar(tmp_path, config=config))


def test_the_committed_sidecar_hosts_the_subagent_tier_it_ships() -> None:
    found = hosted(REPO_ROOT)
    assert {tier.named for tier in found} >= {"CORTEX_MODEL_FILE_SUBAGENT_GPU"}
    assert all(tier.command for tier in found)


def test_the_committed_tier_really_has_the_flags_its_placement_used_to_be_trusted_for() -> None:
    command = hosted(REPO_ROOT)[0].command
    assert "--jinja" in command
    assert command[-len(SUBAGENT_TAIL) :] == SUBAGENT_TAIL
