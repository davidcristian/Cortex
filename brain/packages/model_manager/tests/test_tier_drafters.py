import logging

import pytest
from pydantic import ValidationError

from cortex_model_manager import ModelHostConfig, build_model_host
from cortex_model_manager.config import DEFAULT_CORTEX_FILE
from cortex_model_manager.drafters import DRAFTERS, drafter_file, drafts
from cortex_model_manager.tiers import TierArgs, drafter_flags, with_flags

_E4B = "unsloth/gemma-4-E4B-it-qat-GGUF/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf"
_E4B_DRAFTER = "unsloth/gemma-4-E4B-it-qat-GGUF/mtp-gemma-4-E4B-it-Q8_0.gguf"
_12B_DRAFTER = "unsloth/gemma-4-12B-it-qat-GGUF/mtp-gemma-4-12B-it-Q8_0.gguf"
_OTHER = "small/sub.gguf"
_DRAFT_FLAG = "--model-draft"
_SUBAGENT_TAIL = (
    "--chat-template-kwargs",
    '{"enable_thinking": false}',
    "--reasoning-budget",
    "0",
    "--cache-ram",
    "0",
)
_SERVER_LOGGER = "cortex_model_manager.server"
_OWN_LAYER = ("--spec-type", "draft-mtp", "--spec-draft-n-max", "5")


def _drafting(file: str, length: str = "3") -> tuple[str, ...]:
    return (
        _DRAFT_FLAG,
        f"/models/{file}",
        "--spec-type",
        "draft-mtp",
        "--spec-draft-n-max",
        length,
    )


def _argv(model: str, monkeypatch: pytest.MonkeyPatch, **settings: str) -> tuple[str, ...]:
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    return ModelHostConfig().roster()[model].argv


def test_the_stock_cortex_ends_with_the_drafter_beside_its_file() -> None:
    argv = ModelHostConfig().roster()["cortex"].argv
    assert argv[-8:] == ("--cache-ram", "8192", *_drafting(_12B_DRAFTER))
    assert DRAFTERS[DEFAULT_CORTEX_FILE] == _12B_DRAFTER


def test_an_empty_cortex_drafter_setting_starts_the_tier_without_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv = _argv("cortex", monkeypatch, CORTEX_MODEL_FILE_CORTEX_DRAFT="")
    assert argv[-2:] == ("--cache-ram", "8192")
    assert "--spec-type" not in argv


def test_a_cortex_file_with_no_drafter_beside_it_drafts_only_when_one_is_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _DRAFT_FLAG not in _argv("cortex", monkeypatch, CORTEX_MODEL_FILE_CORTEX="other/c.gguf")
    named = _argv("cortex", monkeypatch, CORTEX_MODEL_FILE_CORTEX_DRAFT="other/d.gguf")
    assert named[-6:] == _drafting("other/d.gguf")


def test_the_cortex_drafter_follows_the_tiers_other_tails(monkeypatch: pytest.MonkeyPatch) -> None:
    argv = _argv("cortex", monkeypatch, CORTEX_REASONING_BUDGET="128", CORTEX_DRAFT_LENGTH="2")
    assert argv[-8:] == ("--reasoning-budget", "128", *_drafting(_12B_DRAFTER, "2"))


def test_each_server_of_the_subagent_pick_keeps_its_tail_and_gets_the_drafter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_MODEL_FILE_SUBAGENT_GPU", _E4B)
    roster = ModelHostConfig().roster()
    for model in ("subagent-gpu", "subagent-gpu-2"):
        assert roster[model].argv[-12:] == (*_SUBAGENT_TAIL, *_drafting(_E4B_DRAFTER))
    assert ModelHostConfig().undrafted() == ""


def test_a_subagent_file_with_no_drafter_beside_it_drafts_only_when_one_is_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plain = _argv("subagent-gpu", monkeypatch, CORTEX_MODEL_FILE_SUBAGENT_GPU=_OTHER)
    assert plain[-6:] == _SUBAGENT_TAIL
    named = _argv(
        "subagent-gpu-2",
        monkeypatch,
        CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT="small/d.gguf",
        CORTEX_DRAFT_LENGTH_SUBAGENT_GPU="5",
    )
    assert named[-12:] == (*_SUBAGENT_TAIL, *_drafting("small/d.gguf", "5"))


def test_an_empty_subagent_drafter_setting_starts_the_pick_without_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv = _argv(
        "subagent-gpu",
        monkeypatch,
        CORTEX_MODEL_FILE_SUBAGENT_GPU=_E4B,
        CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT="",
    )
    assert argv[-6:] == _SUBAGENT_TAIL


def test_a_server_of_two_slots_of_the_pick_still_drafts(monkeypatch: pytest.MonkeyPatch) -> None:
    argv = _argv(
        "subagent-gpu",
        monkeypatch,
        CORTEX_MODEL_FILE_SUBAGENT_GPU=_E4B,
        CORTEX_SUBAGENTS_GPU_PARALLEL="2",
        CORTEX_SUBAGENTS_GPU_SERVERS="1",
    )
    assert argv[-6:] == _drafting(_E4B_DRAFTER)
    assert ModelHostConfig().undrafted() == ""


def test_a_server_of_two_slots_of_an_unlisted_file_is_started_without_its_named_drafter(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    argv = _argv(
        "subagent-gpu",
        monkeypatch,
        CORTEX_MODEL_FILE_SUBAGENT_GPU=_OTHER,
        CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT="small/d.gguf",
        CORTEX_SUBAGENTS_GPU_PARALLEL="2",
    )
    assert argv[-6:] == _SUBAGENT_TAIL
    assert ModelHostConfig().undrafted() == "small/d.gguf"
    with caplog.at_level(logging.WARNING, logger=_SERVER_LOGGER):
        build_model_host(ModelHostConfig())
    [record] = [entry for entry in caplog.records if entry.levelno == logging.WARNING]
    assert record.getMessage() == "starting the GPU subagent servers without their drafter"
    assert (record.__dict__["drafter"], record.__dict__["slots"]) == ("small/d.gguf", 2)


@pytest.mark.parametrize(
    "settings",
    [
        {"CORTEX_MODEL_FILE_SUBAGENT_GPU": _OTHER, "CORTEX_SUBAGENTS_GPU_PARALLEL": "2"},
        {"CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT": "d.gguf", "CORTEX_SUBAGENTS_GPU_PARALLEL": "2"},
        {
            "CORTEX_MODEL_FILE_SUBAGENT_GPU": _OTHER,
            "CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT": "d.gguf",
        },
    ],
)
def test_no_warning_is_logged_where_no_drafter_was_left_out(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, settings: dict[str, str]
) -> None:
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    assert ModelHostConfig().undrafted() == ""
    with caplog.at_level(logging.WARNING, logger=_SERVER_LOGGER):
        build_model_host(ModelHostConfig())
    assert [entry for entry in caplog.records if entry.levelno == logging.WARNING] == []


def test_the_deep_tier_has_its_own_draft_length(monkeypatch: pytest.MonkeyPatch) -> None:
    argv = _argv(
        "brain",
        monkeypatch,
        CORTEX_MODEL_FILE_BRAIN="deep/brain.gguf",
        CORTEX_MODEL_FILE_BRAIN_DRAFT="deep/d.gguf",
        CORTEX_DRAFT_LENGTH_BRAIN="4",
    )
    assert argv[-6:] == _drafting("deep/d.gguf", "4")


@pytest.mark.parametrize(
    "variable",
    ["CORTEX_DRAFT_LENGTH", "CORTEX_DRAFT_LENGTH_BRAIN", "CORTEX_DRAFT_LENGTH_SUBAGENT_GPU"],
)
def test_a_draft_length_of_zero_is_refused(monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    monkeypatch.setenv(variable, "0")
    with pytest.raises(ValidationError):
        ModelHostConfig()


def test_the_drafter_flags_are_one_run_or_nothing() -> None:
    assert drafter_flags("", 3, "/models/m.gguf") == ()
    assert drafter_flags("", 3, "") == ()
    assert drafter_flags("/models/d.gguf", 4, "/models/m.gguf") == (
        _DRAFT_FLAG,
        "/models/d.gguf",
        "--spec-type",
        "draft-mtp",
        "--spec-draft-n-max",
        "4",
    )


def test_a_drafter_that_is_the_model_file_keeps_the_type_and_length_and_names_no_file() -> None:
    assert drafter_flags("/models/m.gguf", 5, "/models/m.gguf") == _OWN_LAYER


@pytest.mark.parametrize(
    ("model", "file", "drafter", "length"),
    [
        (
            "cortex",
            "CORTEX_MODEL_FILE_CORTEX",
            "CORTEX_MODEL_FILE_CORTEX_DRAFT",
            "CORTEX_DRAFT_LENGTH",
        ),
        (
            "brain",
            "CORTEX_MODEL_FILE_BRAIN",
            "CORTEX_MODEL_FILE_BRAIN_DRAFT",
            "CORTEX_DRAFT_LENGTH_BRAIN",
        ),
        (
            "subagent-gpu-2",
            "CORTEX_MODEL_FILE_SUBAGENT_GPU",
            "CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT",
            "CORTEX_DRAFT_LENGTH_SUBAGENT_GPU",
        ),
    ],
)
def test_a_tier_named_as_its_own_drafter_drafts_with_its_layer_and_loads_no_second_file(
    monkeypatch: pytest.MonkeyPatch, model: str, file: str, drafter: str, length: str
) -> None:
    settings = {file: "deep/own.gguf", drafter: "deep/own.gguf", length: "5"}
    argv = _argv(model, monkeypatch, **settings)
    assert argv[-4:] == _OWN_LAYER
    assert _DRAFT_FLAG not in argv
    assert argv.count("/models/deep/own.gguf") == 1


def test_flags_added_to_a_tier_follow_its_own() -> None:
    tier = TierArgs("m", "/models/m.gguf", 8080, 99, 4096, 1, extra=("--jinja",))
    assert with_flags(tier, ("--a", "b")).extra == ("--jinja", "--a", "b")
    assert with_flags(tier, ()) == tier


def test_a_setting_overrides_the_drafter_beside_a_file_even_when_empty() -> None:
    assert drafter_file(None, _E4B) == _E4B_DRAFTER
    assert drafter_file(None, _OTHER) == ""
    assert drafter_file("", _E4B) == ""
    assert drafter_file("x.gguf", _E4B) == "x.gguf"


def test_an_unlisted_file_drafts_on_one_slot_only() -> None:
    assert drafts(_OTHER, 1)
    assert not drafts(_OTHER, 2)
    assert drafts(_E4B, 4)


def test_every_listed_drafter_is_in_its_model_files_directory() -> None:
    for model_file, drafter in DRAFTERS.items():
        assert drafter.rsplit("/", 1)[0] == model_file.rsplit("/", 1)[0]
