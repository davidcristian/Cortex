"""The sidecar's composition root: what ``python -m cortex_model_manager`` actually wires."""

from http import HTTPStatus
from typing import Any, cast

import httpx
import pytest
import uvicorn
from starlette.applications import Starlette

from cortex_model_manager import (
    ModelHostConfig,
    StopBounds,
    build_model_host,
    build_supervisor,
    main,
)


async def test_the_wired_app_serves_the_roster_its_env_declared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_MODEL_FILE_BRAIN", "deep/brain.gguf")
    app = build_model_host(ModelHostConfig())
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://model-host")
    try:
        response = await client.get("/health")
    finally:
        await client.aclose()
    assert response.status_code == HTTPStatus.OK
    assert cast("dict[str, Any]", response.json())["models"] == ["cortex", "brain"]


async def test_the_wiring_hands_over_every_timing_knob_it_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Distinctive values, read back off the two objects the root actually handed them to."""
    monkeypatch.setenv("CORTEX_MODELHOST_STOP_GRACE_S", "7.5")
    monkeypatch.setenv("CORTEX_MODELHOST_REAP_TIMEOUT_S", "11.25")
    monkeypatch.setenv("CORTEX_MODELHOST_PROBE_TIMEOUT_S", "3.25")
    supervisor, client = build_supervisor(ModelHostConfig())
    try:
        assert supervisor.stop_bounds == StopBounds(stop_grace_s=7.5, reap_timeout_s=11.25)
        assert client.timeout == httpx.Timeout(3.25)
    finally:
        await client.aclose()


def test_main_serves_the_configured_interface_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[tuple[str, int, str]] = []

    def fake_run(app: Starlette, *, host: str, port: int, log_level: str) -> None:
        assert isinstance(app, Starlette)
        served.append((host, port, log_level))

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setenv("CORTEX_MODELHOST_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_MODELHOST_BIND_PORT", "9999")
    monkeypatch.setenv("CORTEX_MODELHOST_LOG_LEVEL", "warning")
    main()
    assert served == [("127.0.0.1", 9999, "warning")]
