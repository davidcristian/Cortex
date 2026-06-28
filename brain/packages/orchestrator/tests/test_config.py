"""SeamServerConfig behavior: defaults and CORTEX_SEAM_* environment overrides."""

import pytest

from cortex_orchestrator import SeamServerConfig


@pytest.fixture
def clean_seam_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORTEX_SEAM_HOST", raising=False)
    monkeypatch.delenv("CORTEX_SEAM_PORT", raising=False)


@pytest.mark.usefixtures("clean_seam_env")
def test_defaults_are_loopback_50051() -> None:
    config = SeamServerConfig()
    assert config.host == "127.0.0.1"
    assert config.port == 50051
    assert config.bind_address == "127.0.0.1:50051"


@pytest.mark.usefixtures("clean_seam_env")
def test_env_overrides_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SEAM_HOST", "192.0.2.7")
    monkeypatch.setenv("CORTEX_SEAM_PORT", "50910")
    config = SeamServerConfig()
    assert config.host == "192.0.2.7"
    assert config.port == 50910
    assert config.bind_address == "192.0.2.7:50910"


@pytest.mark.usefixtures("clean_seam_env")
def test_explicit_arguments_beat_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SEAM_PORT", "50910")
    config = SeamServerConfig(port=0)
    assert config.port == 0
