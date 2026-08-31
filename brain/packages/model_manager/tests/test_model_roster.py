"""What the deployment's env becomes: the roster, its argv, and the refused misconfigurations.

The argv assertions are exact on purpose. The resident cortex must come up with byte-identical
flags to the ones the always-on ``llama-cortex`` compose service passed, or a stack that never
escalates would regress merely by being supervised, so this is where that equality is pinned
rather than trusted to a code review of two files.
"""

import pytest
from pydantic import ValidationError

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
    """Flag for flag, in order, including the context size named rather than defaulted.

    llama.cpp's own default pre-allocates a KV cache far larger than the VRAM envelope, which is
    why the tier names a size at all (docker/docker-compose.gpu.yml records the default).
    """
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
    assert roster["subagent-gpu"].argv[-6:] == (
        "3",
        "--jinja",
        "--chat-template-kwargs",
        '{"enable_thinking": false}',
        "--reasoning-budget",
        "0",
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
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", "google/gemma-4-12B/mmproj.gguf")
    argv = ModelHostConfig().roster()["cortex"].argv
    assert argv[-6:-4] == ("--mmproj", "/models/google/gemma-4-12B/mmproj.gguf")


def test_a_deployment_that_names_no_projector_stays_text_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", raising=False)
    assert "--mmproj" not in ModelHostConfig().roster()["cortex"].argv


def test_the_projector_is_resolved_under_the_read_only_models_mount(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_MODELHOST_MODELS_ROOT", "/srv/models")
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", "mmproj.gguf")
    argv = ModelHostConfig().roster()["cortex"].argv
    assert "/srv/models/mmproj.gguf" in argv


def test_a_raised_image_budget_carries_the_micro_batch_up_with_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One knob, two flags, because the pair cannot be split without crashing the server.

    A picture is decoded as one non-causal chunk and llama.cpp asserts the micro-batch is at
    least that large, so a budget above the engine's 512 default without a matching
    ``--ubatch-size`` aborts the process on the first oversized picture. Emitting them together
    is what keeps this knob from being set into that crash.
    """
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", "mmproj.gguf")
    monkeypatch.setenv("CORTEX_IMAGE_MAX_TOKENS", "1024")
    argv = ModelHostConfig().roster()["cortex"].argv
    assert argv[-4:] == ("--image-max-tokens", "1024", "--ubatch-size", "1024")


def test_a_budget_under_the_engine_default_leaves_the_micro_batch_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lowering the budget must not lower the micro-batch, which every text turn also uses."""
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", "mmproj.gguf")
    monkeypatch.setenv("CORTEX_IMAGE_MAX_TOKENS", "128")
    argv = ModelHostConfig().roster()["cortex"].argv
    assert argv[-4:] == ("--image-max-tokens", "128", "--ubatch-size", "512")


def test_the_shipped_default_buys_the_measured_resolution_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A seeing deployment that sets nothing gets the pair the 4K measurement settled on.

    The model's own budget saturates at 266 tokens and reads 6 to 8 of 47 ground-truth strings
    off a 4K desktop; 1024 here, with the brain asking for a 2048 px capture, reads 36 to 38.
    The maintainer took that trade, so it is what an unconfigured stack comes up with.
    """
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", "mmproj.gguf")
    monkeypatch.delenv("CORTEX_IMAGE_MAX_TOKENS", raising=False)
    argv = ModelHostConfig().roster()["cortex"].argv
    assert argv[-4:] == ("--image-max-tokens", "1024", "--ubatch-size", "1024")


def test_a_deployment_can_still_hand_the_budget_back_to_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero is off, and off means an argv naming neither flag rather than one restating the
    engine's own defaults, so a deployment that turns it off gets its VRAM and latency back."""
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", "mmproj.gguf")
    monkeypatch.setenv("CORTEX_IMAGE_MAX_TOKENS", "0")
    argv = ModelHostConfig().roster()["cortex"].argv
    assert "--image-max-tokens" not in argv
    assert "--ubatch-size" not in argv
    assert argv[-2:] == ("--mmproj", "/models/mmproj.gguf")


def test_an_image_budget_without_a_projector_costs_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A text-only tier has no pictures, so the budget must not raise its micro-batch or VRAM."""
    monkeypatch.delenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", raising=False)
    monkeypatch.setenv("CORTEX_IMAGE_MAX_TOKENS", "1024")
    argv = ModelHostConfig().roster()["cortex"].argv
    assert "--image-max-tokens" not in argv
    assert "--ubatch-size" not in argv


def test_a_negative_image_budget_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_IMAGE_MAX_TOKENS", "-1")
    with pytest.raises(ValidationError):
        ModelHostConfig()


def test_a_thinking_budget_reaches_the_cortex_tier_as_the_engines_own_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A budget bounds the cortex tier's thinking rather than ending it.

    Measured on the cortex pick at this very count, the trace falls from 2323 to 2996 characters
    to about 500 and the first word from 10.1 to 12.6 s to 1.7 to 2.6 s, the reply staying the
    same size and ending on its own.
    """
    monkeypatch.setenv("CORTEX_REASONING_BUDGET", "128")
    argv = ModelHostConfig().roster()["cortex"].argv
    assert argv[-2:] == ("--reasoning-budget", "128")


def test_an_unbudgeted_tier_names_no_flag_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default is the argv this repo always came up with, not one restating the engine's."""
    monkeypatch.delenv("CORTEX_REASONING_BUDGET", raising=False)
    assert "--reasoning-budget" not in ModelHostConfig().roster()["cortex"].argv


def test_a_zero_budget_is_a_setting_rather_than_an_absent_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero is llama.cpp's "end the thought immediately", so it must reach the argv; only the
    engine's own -1 means nobody asked."""
    monkeypatch.setenv("CORTEX_REASONING_BUDGET", "0")
    assert ModelHostConfig().roster()["cortex"].argv[-2:] == ("--reasoning-budget", "0")


def test_the_deep_tier_carries_its_own_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two tiers read on opposite arguments, so one knob each: the cortex answers while somebody
    watches, and the deep model was picked for reaching an answer inside its trace at all."""
    monkeypatch.setenv("CORTEX_MODEL_FILE_BRAIN", "deep/brain.gguf")
    monkeypatch.setenv("CORTEX_REASONING_BUDGET_BRAIN", "1024")
    monkeypatch.delenv("CORTEX_REASONING_BUDGET", raising=False)
    roster = ModelHostConfig().roster()
    assert roster["brain"].argv[-2:] == ("--reasoning-budget", "1024")
    assert "--reasoning-budget" not in roster["cortex"].argv


def test_a_budgeted_seeing_cortex_keeps_both_tails(monkeypatch: pytest.MonkeyPatch) -> None:
    """The vision tail and the budget are independent knobs on one tier, so both must survive."""
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", "mmproj.gguf")
    monkeypatch.setenv("CORTEX_IMAGE_MAX_TOKENS", "1024")
    monkeypatch.setenv("CORTEX_REASONING_BUDGET", "256")
    argv = ModelHostConfig().roster()["cortex"].argv
    assert argv[-6:] == (
        "--image-max-tokens",
        "1024",
        "--ubatch-size",
        "1024",
        "--reasoning-budget",
        "256",
    )
    assert "--mmproj" in argv


def test_the_subagent_tier_ends_the_thought_rather_than_bounding_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both levers, and a zero the deployment cannot raise (ADR-0005 thinking-lever addendum).

    The template pair alone was measured not to reach a request carrying a ``response_format``,
    which is every reply a tool-less subagent decodes into the fixed envelope, and the budget is
    what does reach it. A positive count would be a length for a thought this tier does not want
    at all, so the deployment's own budget is deliberately not consulted here.
    """
    monkeypatch.setenv("CORTEX_MODEL_FILE_SUBAGENT_GPU", "small/sub.gguf")
    monkeypatch.setenv("CORTEX_REASONING_BUDGET", "128")
    argv = ModelHostConfig().roster()["subagent-gpu"].argv
    assert argv[-4:] == (
        "--chat-template-kwargs",
        '{"enable_thinking": false}',
        "--reasoning-budget",
        "0",
    )
    assert "128" not in argv


def test_a_budget_below_the_engines_own_default_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """-1 is the floor because it is llama.cpp's own word for unrestricted; -2 says nothing."""
    monkeypatch.setenv("CORTEX_REASONING_BUDGET", "-2")
    with pytest.raises(ValidationError):
        ModelHostConfig()
