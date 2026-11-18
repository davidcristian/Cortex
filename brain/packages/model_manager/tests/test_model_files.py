import pytest
from process_fakes import FakeChildProcesses, FakeProbe

from cortex_core import ModelHostState
from cortex_model_manager import (
    ModelFiles,
    ModelHostConfig,
    ModelSupervisor,
    SupervisorError,
    build_supervisor,
    tier_settings,
)

_DRAFTER = "/models/drafts/mtp.gguf"
_PROJECTOR = "/models/vision/mmproj.gguf"


def _config(monkeypatch: pytest.MonkeyPatch, **settings: str) -> ModelHostConfig:
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX", "main/cortex.gguf")
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX_DRAFT", "drafts/mtp.gguf")
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", "vision/mmproj.gguf")
    monkeypatch.setenv("CORTEX_MODEL_FILE_BRAIN", "deep/brain.gguf")
    monkeypatch.setenv("CORTEX_MODEL_FILE_SUBAGENT_GPU", "small/sub.gguf")
    monkeypatch.setenv("CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT", "drafts/mtp.gguf")
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    return ModelHostConfig()


def _files(config: ModelHostConfig, *absent: str) -> ModelFiles:
    return ModelFiles(tier_settings(config), lambda path: path not in absent)


def test_every_roster_id_has_the_setting_part_of_its_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(monkeypatch)
    assert tier_settings(config) == {
        "cortex": "CORTEX",
        "brain": "BRAIN",
        "subagent-gpu": "SUBAGENT_GPU",
        "subagent-gpu-2": "SUBAGENT_GPU",
    }
    assert set(tier_settings(config)) == set(config.roster())


def test_a_tier_whose_files_are_all_there_has_nothing_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(monkeypatch)
    files = _files(config)
    assert [files.missing(spec) for spec in config.roster().values()] == [None] * 4


@pytest.mark.parametrize(
    ("model", "absent", "setting"),
    [
        ("cortex", "/models/main/cortex.gguf", "CORTEX_MODEL_FILE_CORTEX "),
        ("cortex", _PROJECTOR, "CORTEX_MODEL_FILE_CORTEX_MMPROJ "),
        ("cortex", _DRAFTER, "CORTEX_MODEL_FILE_CORTEX_DRAFT "),
        ("brain", "/models/deep/brain.gguf", "CORTEX_MODEL_FILE_BRAIN "),
        ("subagent-gpu-2", _DRAFTER, "CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT "),
    ],
)
def test_an_absent_file_is_named_with_the_setting_that_names_it(
    monkeypatch: pytest.MonkeyPatch, model: str, absent: str, setting: str
) -> None:
    config = _config(monkeypatch)
    gap = _files(config, absent).missing(config.roster()[model])
    assert gap is not None
    assert gap.startswith(f"{setting}names '{absent}', which is not a file")


def test_a_drafter_that_is_the_tiers_own_file_is_checked_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(monkeypatch, CORTEX_MODEL_FILE_BRAIN_DRAFT="deep/brain.gguf")
    asked: list[str] = []
    files = ModelFiles(tier_settings(config), lambda path: asked.append(path) is None)
    assert files.missing(config.roster()["brain"]) is None
    assert asked == ["/models/deep/brain.gguf"]


async def test_a_start_with_an_absent_drafter_fails_before_any_process_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(monkeypatch)
    processes = FakeChildProcesses()
    supervisor = ModelSupervisor(
        config.roster(), processes, FakeProbe(), files=_files(config, _DRAFTER)
    )
    with pytest.raises(
        SupervisorError,
        match=f"could not start 'cortex': CORTEX_MODEL_FILE_CORTEX_DRAFT names '{_DRAFTER}'",
    ):
        await supervisor.start("cortex")
    assert processes.spawned == []
    assert (await supervisor.status("cortex")).state is ModelHostState.STOPPED
    await supervisor.start("brain")
    assert [child.argv for child in processes.spawned] == [config.roster()["brain"].argv]


async def test_the_wiring_checks_the_files_in_the_containers_own_models_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    root = tmp_path_factory.mktemp("models")
    (root / "main").mkdir()
    (root / "main" / "cortex.gguf").write_bytes(b"")
    config = _config(
        monkeypatch, CORTEX_MODELHOST_MODELS_ROOT=str(root), CORTEX_MODEL_FILE_CORTEX_MMPROJ=""
    )
    supervisor, client = build_supervisor(config)
    await client.aclose()
    with pytest.raises(SupervisorError) as refused:
        await supervisor.start("cortex")
    assert f"CORTEX_MODEL_FILE_CORTEX_DRAFT names '{root}/drafts/mtp.gguf'" in str(refused.value)
