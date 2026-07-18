"""What the deployment's env becomes: the roster, its argv, and the misconfigurations refused.

The argv assertions are exact on purpose. The resident cortex must come up with byte-identical
flags to the ones the always-on ``llama-cortex`` compose service passed, or a stack that never
escalates would regress merely by being supervised, so this is where that equality is pinned
rather than trusted to a code review of two files.
"""

import pytest

from cortex_model_manager import (
    ModelHostConfig,
    ModelSpec,
    RosterError,
    TierArgs,
    build_roster,
    llama_server_argv,
    tier_spec,
)

_BIN = "/app/llama-server"
# The child serves the compose network, which is what the flag pair below has to say.
_BIND_ALL = "0.0.0.0"  # noqa: S104 - asserted as the flag value, not bound by this process
_CORTEX_GGUF = "google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf"


def _tier(**overrides: object) -> TierArgs:
    fields: dict[str, object] = {
        "model": "cortex",
        "model_path": "/models/c.gguf",
        "port": 8080,
        "ngl": 99,
        "ctx_size": 4096,
        "parallel": 1,
    }
    return TierArgs(**(fields | overrides))  # pyright: ignore[reportArgumentType]


def test_the_argv_is_the_compose_command_it_replaces() -> None:
    """Flag for flag, in order, including the explicit context llama.cpp's default would blow."""
    assert llama_server_argv(_BIN, _tier(model_path=f"/models/{_CORTEX_GGUF}", ctx_size=16384)) == (
        _BIN,
        "--model",
        f"/models/{_CORTEX_GGUF}",
        "--host",
        _BIND_ALL,
        "--port",
        "8080",
        "-ngl",
        "99",
        "--ctx-size",
        "16384",
        "--parallel",
        "1",
        "--jinja",
    )


def test_a_tiers_tail_rides_extra_rather_than_a_flag_per_knob() -> None:
    """The subagent tier's reasoning-off pair, which is the only tail any tier carries today."""
    argv = llama_server_argv(_BIN, _tier(extra=("--chat-template-kwargs", '{"a": false}')))
    assert argv[-3:] == ("--jinja", "--chat-template-kwargs", '{"a": false}')


def test_a_spec_carries_its_port_and_the_loopback_url_its_own_probe_uses() -> None:
    spec = tier_spec(_BIN, _tier(port=8083))
    assert (spec.model, spec.port) == ("cortex", 8083)
    assert spec.health_url == "http://127.0.0.1:8083/health"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("model", "", "non-empty logical id"),
        ("port", 0, "must be in 1..65535"),
        ("port", 70000, "must be in 1..65535"),
        ("argv", (), "must name a binary"),
    ],
)
def test_a_spec_refuses_what_could_not_be_run(field: str, value: object, message: str) -> None:
    fields: dict[str, object] = {"model": "cortex", "port": 8080, "argv": (_BIN,)}
    with pytest.raises(RosterError, match=message):
        ModelSpec(**(fields | {field: value}))  # pyright: ignore[reportArgumentType]


def test_two_tiers_sharing_a_port_are_refused_at_boot() -> None:
    """The misconfiguration that would silently defeat a swap, caught where it can still be fixed.

    Measured: the second child dies at once with a bind failure while the first keeps answering
    ``/health`` on that port, so nothing downstream would look wrong until a swap left the old
    weights resident.
    """
    with pytest.raises(RosterError, match="share port 8080"):
        build_roster(
            [tier_spec(_BIN, _tier(model="cortex")), tier_spec(_BIN, _tier(model="brain"))]
        )


def test_two_tiers_sharing_an_id_are_refused_at_boot() -> None:
    with pytest.raises(RosterError, match="duplicate logical model id in the roster: 'cortex'"):
        build_roster([tier_spec(_BIN, _tier(port=8080)), tier_spec(_BIN, _tier(port=8081))])


def test_the_stock_deployment_hosts_the_cortex_and_nothing_it_has_no_artifact_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No deep-model pick exists yet, so a stock model host answers 404 for it rather than
    spawning a doomed process."""
    for name in ("CORTEX_MODEL_FILE_BRAIN", "CORTEX_MODEL_FILE_SUBAGENT_GPU"):
        monkeypatch.delenv(name, raising=False)
    roster = ModelHostConfig().roster()
    assert list(roster) == ["cortex"]
    assert roster["cortex"].argv == llama_server_argv(
        _BIN, _tier(model_path=f"/models/{_CORTEX_GGUF}", ctx_size=16384)
    )


def test_naming_every_tiers_artifact_hosts_all_three_on_the_documented_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The full ADR-0030 topology: cortex 8080, deep model 8081, GPU-placed subagent 8083."""
    monkeypatch.setenv("CORTEX_MODEL_FILE_BRAIN", "deep/brain.gguf")
    monkeypatch.setenv("CORTEX_MODEL_FILE_SUBAGENT_GPU", "small/sub.gguf")
    monkeypatch.setenv("CORTEX_MODEL_BRAIN", "deep")
    monkeypatch.setenv("CORTEX_CTX_SIZE_BRAIN", "32768")
    monkeypatch.setenv("CORTEX_SUBAGENTS_PARALLEL", "3")
    roster = ModelHostConfig().roster()
    assert {model: spec.port for model, spec in roster.items()} == {
        "cortex": 8080,
        "deep": 8081,
        "subagent-gpu": 8083,
    }
    assert roster["deep"].argv[:3] == (_BIN, "--model", "/models/deep/brain.gguf")
    assert "32768" in roster["deep"].argv
    # The GPU-placed subagent is the tier ADR-0012's host half was waiting for: whole model on the
    # GPU, reasoning off, one server slot per admitted subagent.
    assert roster["subagent-gpu"].argv[-4:] == (
        "3",
        "--jinja",
        "--chat-template-kwargs",
        '{"enable_thinking": false}',
    )
    assert "-ngl" in roster["subagent-gpu"].argv
    assert roster["subagent-gpu"].argv[roster["subagent-gpu"].argv.index("-ngl") + 1] == "99"


def test_the_models_root_is_joined_without_doubling_a_separator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_MODELHOST_MODELS_ROOT", "/mnt/models/")
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX", "a/b.gguf")
    assert "/mnt/models/a/b.gguf" in ModelHostConfig().roster()["cortex"].argv


def test_naming_a_projector_gives_the_cortex_tier_eyes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The vision projector rides the cortex tier's argv (ADR-0029), not a compose command
    block: the model host has owned llama-server's flags since it replaced the always-on
    service. The brain then discovers the capability from the running server's /props rather
    than from a second flag here that could disagree with it."""
    monkeypatch.setenv("CORTEX_MMPROJ_FILE_CORTEX", "google/gemma-4-12B/mmproj.gguf")
    argv = ModelHostConfig().roster()["cortex"].argv
    assert argv[-2:] == ("--mmproj", "/models/google/gemma-4-12B/mmproj.gguf")


def test_a_deployment_that_names_no_projector_stays_text_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORTEX_MMPROJ_FILE_CORTEX", raising=False)
    assert "--mmproj" not in ModelHostConfig().roster()["cortex"].argv


def test_the_projector_is_resolved_under_the_read_only_models_mount(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_MODELHOST_MODELS_ROOT", "/srv/models")
    monkeypatch.setenv("CORTEX_MMPROJ_FILE_CORTEX", "mmproj.gguf")
    argv = ModelHostConfig().roster()["cortex"].argv
    assert "/srv/models/mmproj.gguf" in argv
