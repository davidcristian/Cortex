"""The daemon's two OS seams: the asyncio child wrapper and the HTTP health probe.

Both are the thinnest wrappers that can hold a real call, so the gated tests here drive them over
a stand-in ``Process`` and an ``httpx.MockTransport``; the real spawn and the real socket are
exercised by the ``integration``-marked live suite (AGENTS.md gate 3).
"""

import asyncio
from http import HTTPStatus
from typing import cast

import httpx
import pytest

from cortex_model_manager import AsyncioChild, AsyncioChildProcesses, HttpHealthProbe


class _StandInProcess:
    """What ``asyncio.create_subprocess_exec`` hands back, minus the process.

    ``lookup_error`` is the one real race the wrapper exists to absorb: a child that exited between
    the status read and the signal, which the OS reports as ``ProcessLookupError``.
    """

    def __init__(self, *, lookup_error: bool = False) -> None:
        self.pid = 4242
        self.returncode: int | None = None
        self.calls: list[str] = []
        self._lookup_error = lookup_error

    def terminate(self) -> None:
        self.calls.append("terminate")
        self._maybe_gone()

    def kill(self) -> None:
        self.calls.append("kill")
        self._maybe_gone()

    async def wait(self) -> int:
        self.returncode = 0
        return 0

    def _maybe_gone(self) -> None:
        if self._lookup_error:
            msg = "no such process"
            raise ProcessLookupError(msg)


def _wrapped(process: _StandInProcess) -> AsyncioChild:
    return AsyncioChild(cast("asyncio.subprocess.Process", process))


async def test_the_wrapper_passes_the_process_through_verbatim() -> None:
    process = _StandInProcess()
    child = _wrapped(process)
    assert (child.pid, child.returncode) == (4242, None)
    child.terminate()
    child.kill()
    assert await child.wait() == 0
    assert (process.calls, child.returncode) == (["terminate", "kill"], 0)


@pytest.mark.parametrize("signal_name", ["terminate", "kill"])
async def test_signalling_a_child_that_already_exited_is_not_a_failure(signal_name: str) -> None:
    """Ending a process that ended itself is the outcome the caller wanted, not an error."""
    process = _StandInProcess(lookup_error=True)
    getattr(_wrapped(process), signal_name)()
    assert process.calls == [signal_name]


async def test_the_spawner_execs_the_argv_it_is_given(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one real OS write, asserted as the argv that reached ``create_subprocess_exec``."""
    seen: list[tuple[str, ...]] = []

    async def fake_exec(*argv: str) -> _StandInProcess:
        seen.append(argv)
        return _StandInProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    argv = ("/app/llama-server", "--port", "8080")
    child = await AsyncioChildProcesses().spawn(argv)
    assert seen == [argv]
    assert child.pid == 4242


def _probe(handler: httpx.MockTransport) -> HttpHealthProbe:
    return HttpHealthProbe(httpx.AsyncClient(transport=handler))


async def test_a_two_hundred_is_serving_and_a_five_oh_three_is_not() -> None:
    """The measured shape of a real load: 503 ``Loading model`` for minutes, then 200 ``ok``."""

    def loading(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            HTTPStatus.SERVICE_UNAVAILABLE, json={"error": {"message": "Loading model"}}
        )

    def ready(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(HTTPStatus.OK, json={"status": "ok"})

    url = "http://127.0.0.1:8080/health"
    assert await _probe(httpx.MockTransport(loading)).serving(url) is False
    assert await _probe(httpx.MockTransport(ready)).serving(url) is True


async def test_a_socket_that_refuses_is_not_serving_rather_than_an_error() -> None:
    """The first fraction of a second of every start, and the whole of a dead one."""

    def refused(request: httpx.Request) -> httpx.Response:
        msg = "connection refused"
        raise httpx.ConnectError(msg, request=request)

    assert (
        await _probe(httpx.MockTransport(refused)).serving("http://127.0.0.1:8081/health") is False
    )
