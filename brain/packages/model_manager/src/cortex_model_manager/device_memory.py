"""How much of the card is free: the daemon's third OS seam (port + ``nvidia-smi`` adapter)."""

import asyncio
import logging
from typing import Protocol

from cortex_core import DeviceMemory

_logger = logging.getLogger(__name__)

# One row per visible GPU, "free, total" in MiB and nothing else: no header to skip and no unit to
# strip, so the parse below is two integers or nothing.
_QUERY = ("--query-gpu=memory.free,memory.total", "--format=csv,noheader,nounits")


class DeviceMemoryProbe(Protocol):
    """How much device memory is free and how much exists, or ``None`` for a host with no card."""

    async def read(self) -> DeviceMemory | None: ...


class NoDeviceMemory:
    """The default probe: a daemon nobody gave a card reports none, without asking anything.

    What a CPU-only deployment and the test suites get. It exists so the "no reading" path is a
    real object rather than a ``None`` collaborator every caller has to branch on.
    """

    async def read(self) -> DeviceMemory | None:
        return None


class NvidiaSmiMemory:
    """The real probe: one bounded ``nvidia-smi`` call, parsed strictly or not at all."""

    def __init__(self, binary: str, timeout_s: float) -> None:
        self._binary = binary
        self._timeout_s = timeout_s

    async def read(self) -> DeviceMemory | None:
        """The card's free and total MiB, or ``None`` when this host cannot answer for one."""
        output = await self._query()
        return None if output is None else _parse(output)

    async def _query(self) -> str | None:
        """Run the query under its bound, treating every way it can go wrong as no reading."""
        try:
            async with asyncio.timeout(self._timeout_s):
                process = await asyncio.create_subprocess_exec(
                    self._binary,
                    *_QUERY,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await process.communicate()
        except (OSError, TimeoutError) as err:
            # The normal case on a machine with no GPU: the binary is not in the image at all.
            _logger.info(
                "no device memory reading is available from %s: %s",
                self._binary,
                err,
                extra={"binary": self._binary, "error": str(err)},
            )
            return None
        if process.returncode != 0:
            _logger.warning(
                "the device memory query exited with code %s",
                process.returncode,
                extra={"binary": self._binary, "returncode": process.returncode},
            )
            return None
        return stdout.decode(errors="replace")


def _parse(output: str) -> DeviceMemory | None:
    """The one row of two integers, or ``None`` when that is not what came back."""
    rows = [row for row in output.splitlines() if row.strip()]
    if len(rows) != 1:
        _logger.warning(
            "a device memory reading needs exactly one visible GPU; got %d",
            len(rows),
            extra={"rows": len(rows)},
        )
        return None
    fields = rows[0].split(",")
    try:
        free_mib, total_mib = (int(field.strip()) for field in fields)
    except ValueError:
        _logger.warning(
            "a device memory reading could not be parsed", extra={"reading": rows[0].strip()}
        )
        return None
    return DeviceMemory(free_mib=free_mib, total_mib=total_mib)
