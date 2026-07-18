"""The sidecar's composition root: what ``python -m cortex_model_manager`` actually wires.

``main`` is exercised with ``uvicorn.run`` replaced, the ``cortex_email`` precedent: the recorded
call is the assertion, because the one thing worth pinning is that the bind address and port come
from config rather than from a literal.

Distrust-green proofs, each applied to production code alone with the whole
``packages/model_manager`` suite re-run, so the counts are measured:

- collapsing ``build_supervisor`` to ``httpx.AsyncClient()`` plus a ``ModelSupervisor`` on its
  defaults (all three timing knobs ignored) reddens exactly 1 case,
  ``test_the_wiring_hands_over_every_timing_knob_it_reads``; replacing any single one of the three
  with its default literal reddens the same one case, and nothing else in the package sees these
  knobs at all;
- having ``ModelSupervisor`` store the defaults instead of the bounds it was constructed with
  reddens 2: that case and ``test_api.py``'s health case, which reads them back off the wire.
"""

import logging
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
    """Distinctive values, read back off the two objects the root actually handed them to.

    Nothing else in this process observes these three, so without this the root could ignore all
    of them: the daemon would evict on the defaults while the runbook's pairing rule was being
    reasoned about the numbers the deployment set. The probe client's deadline is asserted the way
    the brain-side twin asserts its control client's.
    """
    monkeypatch.setenv("CORTEX_MODELHOST_STOP_GRACE_S", "7.5")
    monkeypatch.setenv("CORTEX_MODELHOST_REAP_TIMEOUT_S", "11.25")
    monkeypatch.setenv("CORTEX_MODELHOST_PROBE_TIMEOUT_S", "3.25")
    supervisor, client = build_supervisor(ModelHostConfig())
    try:
        assert supervisor.stop_bounds == StopBounds(stop_grace_s=7.5, reap_timeout_s=11.25)
        assert client.timeout == httpx.Timeout(3.25)
    finally:
        await client.aclose()


def test_main_serves_the_configured_interface_and_port_and_configures_the_root_logger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The root logger is the sidecar's whole diagnosis surface, and nothing else configures it.

    ``uvicorn.run`` configures uvicorn's own loggers and leaves root alone, so measured in the
    image: without this call every lifecycle line the package logs at INFO is dropped and the one
    WARNING that escapes goes through logging's last-resort handler, which renders neither the
    level nor the timestamp. The recorded call is the assertion here (the effect is a global, and
    the container log is where it is verified for real).
    """
    served: list[tuple[str, int, str]] = []
    configured: list[str] = []

    def fake_run(app: Starlette, *, host: str, port: int, log_level: str) -> None:
        assert isinstance(app, Starlette)
        served.append((host, port, log_level))

    def fake_basic_config(*, level: str) -> None:
        configured.append(level)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)
    monkeypatch.setenv("CORTEX_MODELHOST_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_MODELHOST_BIND_PORT", "9999")
    monkeypatch.setenv("CORTEX_MODELHOST_LOG_LEVEL", "warning")
    main()
    assert served == [("127.0.0.1", 9999, "warning")]
    assert configured == ["WARNING"]
