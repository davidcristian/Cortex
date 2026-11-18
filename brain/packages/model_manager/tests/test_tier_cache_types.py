import pytest
from pydantic import ValidationError

from cortex_model_manager import ModelHostConfig
from cortex_model_manager.tiers import cache_flags, draft_and_cache_flags

_MODEL_CACHE = ("--cache-type-k", "q8_0", "--cache-type-v", "q8_0")
_DRAFT_CACHE = ("--cache-type-k-draft", "q8_0", "--cache-type-v-draft", "q8_0")
_E4B = "unsloth/gemma-4-E4B-it-qat-GGUF/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf"
_VARIABLES = {
    "cortex": "CORTEX_KV_CACHE_TYPE",
    "brain": "CORTEX_KV_CACHE_TYPE_BRAIN",
    "subagent-gpu": "CORTEX_KV_CACHE_TYPE_SUBAGENT_GPU",
    "subagent-gpu-2": "CORTEX_KV_CACHE_TYPE_SUBAGENT_GPU",
}
_EVERY_TAIL = {
    "CORTEX_MODEL_FILE_CORTEX_MMPROJ": "vision/mmproj.gguf",
    "CORTEX_REASONING_BUDGET": "128",
    "CORTEX_REASONING_BUDGET_BRAIN": "512",
    "CORTEX_MODEL_FILE_BRAIN": "deep/own.gguf",
    "CORTEX_MODEL_FILE_BRAIN_DRAFT": "deep/own.gguf",
    "CORTEX_MODEL_FILE_SUBAGENT_GPU": _E4B,
}


def _roster(monkeypatch: pytest.MonkeyPatch, **settings: str) -> dict[str, tuple[str, ...]]:
    for name, value in {**_EVERY_TAIL, **settings}.items():
        monkeypatch.setenv(name, value)
    return {model: spec.argv for model, spec in ModelHostConfig().roster().items()}


def test_every_tier_keeps_the_engines_cache_type_by_naming_no_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roster = _roster(monkeypatch)
    assert set(roster) == set(_VARIABLES)
    for argv in roster.values():
        assert not [item for item in argv if item.startswith("--cache-type")]


@pytest.mark.parametrize("model", list(_VARIABLES))
def test_a_tiers_cache_type_follows_its_drafter_and_reaches_no_other_tier(
    monkeypatch: pytest.MonkeyPatch, model: str
) -> None:
    roster = _roster(monkeypatch, **{_VARIABLES[model]: "q8_0"})
    assert roster[model][-10:-8] == ("--spec-draft-n-max", "3")
    assert roster[model][-8:] == (*_MODEL_CACHE, *_DRAFT_CACHE)
    others = [name for name, variable in _VARIABLES.items() if variable != _VARIABLES[model]]
    for other in others:
        assert "--cache-type-k" not in roster[other]


@pytest.mark.parametrize(
    ("model", "drafter"),
    [
        ("cortex", "CORTEX_MODEL_FILE_CORTEX_DRAFT"),
        ("brain", "CORTEX_MODEL_FILE_BRAIN_DRAFT"),
        ("subagent-gpu-2", "CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT"),
    ],
)
def test_a_tier_that_does_not_draft_names_no_cache_type_for_a_drafter(
    monkeypatch: pytest.MonkeyPatch, model: str, drafter: str
) -> None:
    argv = _roster(monkeypatch, **{_VARIABLES[model]: "q8_0", drafter: ""})[model]
    assert argv[-4:] == _MODEL_CACHE
    assert "--cache-type-k-draft" not in argv
    assert "--spec-type" not in argv


def test_a_subagent_server_started_without_its_drafter_names_no_cache_type_for_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roster = _roster(
        monkeypatch,
        CORTEX_KV_CACHE_TYPE_SUBAGENT_GPU="q8_0",
        CORTEX_MODEL_FILE_SUBAGENT_GPU="small/sub.gguf",
        CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT="small/d.gguf",
        CORTEX_SUBAGENTS_GPU_PARALLEL="2",
    )
    assert roster["subagent-gpu"][-6:] == ("--cache-ram", "0", *_MODEL_CACHE)


@pytest.mark.parametrize("variable", sorted(set(_VARIABLES.values())))
@pytest.mark.parametrize("unknown", ["q4_0", "Q8_0", ""])
def test_a_cache_type_with_no_rows_is_refused(
    monkeypatch: pytest.MonkeyPatch, variable: str, unknown: str
) -> None:
    monkeypatch.setenv(variable, unknown)
    with pytest.raises(ValidationError):
        ModelHostConfig()


def test_the_engines_own_type_is_accepted_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = dict.fromkeys(_VARIABLES.values(), "f16")
    for argv in _roster(monkeypatch, **settings).values():
        assert "--cache-type-k" not in argv


def test_no_tier_names_a_flash_attention_setting_so_an_8_bit_cache_is_never_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roster = _roster(monkeypatch, **dict.fromkeys(_VARIABLES.values(), "q8_0"))
    assert set(roster) == set(_VARIABLES)
    for argv in roster.values():
        assert _MODEL_CACHE[2:] == argv[argv.index("--cache-type-v") :][:2]
        assert not [item for item in argv if item in ("-fa", "--flash-attn")]


def test_the_cache_flags_are_nothing_at_16_bits_and_one_type_for_the_whole_server() -> None:
    assert cache_flags("f16", drafting=True) == ()
    assert cache_flags("f16", drafting=False) == ()
    assert cache_flags("q8_0", drafting=False) == _MODEL_CACHE
    assert cache_flags("q8_0", drafting=True) == (*_MODEL_CACHE, *_DRAFT_CACHE)


def test_the_cache_flags_follow_the_drafter_flags() -> None:
    assert draft_and_cache_flags("", 3, "/models/m.gguf", "f16") == ()
    assert draft_and_cache_flags("", 3, "/models/m.gguf", "q8_0") == _MODEL_CACHE
    assert draft_and_cache_flags("/models/m.gguf", 5, "/models/m.gguf", "q8_0") == (
        "--spec-type",
        "draft-mtp",
        "--spec-draft-n-max",
        "5",
        *_MODEL_CACHE,
        *_DRAFT_CACHE,
    )
