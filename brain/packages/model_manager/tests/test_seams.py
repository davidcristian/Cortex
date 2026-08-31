"""The daemon's two OS seams: the asyncio child wrapper and the HTTP health probe.

Both are the thinnest wrappers that can hold a real call, so the gated tests here drive them over
a stand-in ``Process`` and an ``httpx.MockTransport``; the real spawn and the real socket are
exercised by the ``integration``-marked live suite (AGENTS.md gate 3).

These checks were proved able to fail, over the ``packages/model_manager`` suite: returning a
literal from ``AsyncioChild.pid`` instead of the wrapped process's own fails exactly 1 case either
way, and which one depends on the literal, so no literal passes both. ``4242`` fails
``test_the_spawner_execs_the_argv_it_is_given`` and ``4243`` fails
``test_the_wrapper_passes_the_process_through_verbatim``.
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

    ``pid`` is required rather than defaulted, and the two tests that read it back through the
    wrapper use **different** values: a wrapper that returned a literal instead of the process's
    own pid could otherwise satisfy both, and the pid is what the supervisor logs and what an
    operator kills by.
    """

    def __init__(self, pid: int, *, lookup_error: bool = False) -> None:
        self.pid = pid
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
    process = _StandInProcess(pid=4242)
    child = _wrapped(process)
    assert (child.pid, child.returncode) == (process.pid, None)
    child.terminate()
    child.kill()
    assert await child.wait() == 0
    assert (process.calls, child.returncode) == (["terminate", "kill"], 0)


@pytest.mark.parametrize("signal_name", ["terminate", "kill"])
async def test_signalling_a_child_that_already_exited_is_not_a_failure(signal_name: str) -> None:
    """Signalling a process that already exited raises nothing: the caller wanted it ended."""
    process = _StandInProcess(pid=4242, lookup_error=True)
    getattr(_wrapped(process), signal_name)()
    assert process.calls == [signal_name]


async def test_the_spawner_execs_the_argv_it_is_given(monkeypatch: pytest.MonkeyPatch) -> None:
    """The spawner's one OS write is asserted as the argv that reached
    ``create_subprocess_exec``."""
    seen: list[tuple[str, ...]] = []
    spawned: list[_StandInProcess] = []

    async def fake_exec(*argv: str) -> _StandInProcess:
        seen.append(argv)
        # A different pid from the other test's, so the wrapper cannot pass both on a literal.
        spawned.append(_StandInProcess(pid=4243))
        return spawned[-1]

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    argv = ("/app/llama-server", "--port", "8080")
    child = await AsyncioChildProcesses().spawn(argv)
    assert seen == [argv]
    assert child.pid == spawned[0].pid == 4243


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
    """A refused socket reads as not serving, which is every start's first moments and all of a
    dead one."""

    def refused(request: httpx.Request) -> httpx.Response:
        msg = "connection refused"
        raise httpx.ConnectError(msg, request=request)

    assert (
        await _probe(httpx.MockTransport(refused)).serving("http://127.0.0.1:8081/health") is False
    )
