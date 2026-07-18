"""The sidecar's composition root: what ``python -m cortex_model_manager`` actually wires.

``main`` is exercised with ``uvicorn.run`` replaced, the ``cortex_email`` precedent: the recorded
call is the assertion, because the one thing worth pinning is that the bind address and port come
from config rather than from a literal.
"""

from http import HTTPStatus
from typing import Any, cast

import httpx
import pytest
import uvicorn
from starlette.applications import Starlette

from cortex_model_manager import ModelHostConfig, build_model_host, main


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
