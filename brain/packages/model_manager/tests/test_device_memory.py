import asyncio
import logging

import pytest

from cortex_core import DeviceMemory, PlainFormatter
from cortex_model_manager import NoDeviceMemory, NvidiaSmiMemory

_BINARY = "/usr/bin/nvidia-smi"


class _StandInProcess:
    """Stand in for what ``create_subprocess_exec`` hands back: an exit code and one stdout."""

    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.returncode = returncode
        self._stdout = stdout

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout.encode(), b""


def _answering(
    monkeypatch: pytest.MonkeyPatch, stdout: str, returncode: int = 0
) -> list[tuple[str, ...]]:
    """Patch the exec so the adapter talks to a stand-in, and record the argv it asked for."""
    seen: list[tuple[str, ...]] = []

    async def fake_exec(*argv: str, **kwargs: object) -> _StandInProcess:
        del kwargs
        seen.append(argv)
        return _StandInProcess(stdout, returncode)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return seen


def _rendered(caplog: pytest.LogCaptureFixture) -> str:
    """Render the one captured line as an operator reads it, fields and all."""
    (record,) = caplog.records
    return PlainFormatter().format(record)


async def test_a_host_with_no_probe_reports_no_card_without_asking_anything() -> None:
    assert await NoDeviceMemory().read() is None


async def test_a_single_row_is_read_as_free_then_total(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _answering(monkeypatch, "22484, 24463\n")
    assert await NvidiaSmiMemory(_BINARY, 5.0).read() == DeviceMemory(
        free_mib=22484, total_mib=24463
    )
    assert seen == [
        (_BINARY, "--query-gpu=memory.free,memory.total", "--format=csv,noheader,nounits")
    ]


async def test_more_than_one_visible_gpu_is_no_reading_rather_than_a_guess(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _answering(monkeypatch, "22484, 24463\n8000, 8188\n")
    with caplog.at_level(logging.WARNING, logger="cortex_model_manager.device_memory"):
        assert await NvidiaSmiMemory(_BINARY, 5.0).read() is None
    assert "exactly one visible GPU" in caplog.text
    assert "rows=2" in _rendered(caplog)


async def test_a_reading_that_is_not_two_integers_is_no_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _answering(monkeypatch, "[N/A], [N/A]\n")
    assert await NvidiaSmiMemory(_BINARY, 5.0).read() is None


async def test_a_row_with_the_wrong_number_of_fields_is_no_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _answering(monkeypatch, "22484\n")
    assert await NvidiaSmiMemory(_BINARY, 5.0).read() is None


async def test_a_failed_query_is_no_reading_rather_than_an_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _answering(monkeypatch, "", returncode=9)
    with caplog.at_level(logging.WARNING, logger="cortex_model_manager.device_memory"):
        assert await NvidiaSmiMemory(_BINARY, 5.0).read() is None
    assert _rendered(caplog) == (
        "WARNING:cortex_model_manager.device_memory:"
        f"the device memory query exited with a non-zero code binary={_BINARY} returncode=9"
    )


async def test_a_missing_binary_is_the_normal_answer_on_a_machine_with_no_gpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def missing(*argv: str, **kwargs: object) -> _StandInProcess:
        del argv, kwargs
        msg = "no such file"
        raise FileNotFoundError(msg)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", missing)
    assert await NvidiaSmiMemory(_BINARY, 5.0).read() is None


async def test_a_query_that_hangs_is_bounded_rather_than_holding_the_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Hanging:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            await asyncio.sleep(30)
            return b"", b""  # pragma: no cover - the bound above is what ends this call

    async def hanging(*argv: str, **kwargs: object) -> _Hanging:
        del argv, kwargs
        return _Hanging()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", hanging)
    assert await NvidiaSmiMemory(_BINARY, 0.01).read() is None
