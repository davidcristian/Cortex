"""How much of the card is free: the daemon's third OS seam (port + ``nvidia-smi`` adapter).

The supervisor container is the only process in the stack that can see the GPU. The brain's own
container has no device reserved and never will, so a fit check on the brain's side is worth
exactly what this reports, which is why the reading rides the control API the brain already talks
to (``GET /health``) rather than becoming a second thing to configure.

Deliberate shape, each part paid for by something measured:

- **``nvidia-smi``, not a library.** The binary is injected into the container by the NVIDIA
  container toolkit alongside the driver, so it is present wherever a GPU is reserved and absent
  wherever one is not, which is exactly the condition this seam has to report. A Python NVML
  binding would add a dependency to the image for one number and would still be a wrapper around
  the same driver library.
- **Every failure is "no reading", never an exception.** A missing binary, a non-zero exit, a body
  that will not parse: all of them mean the daemon cannot see a card, which is a normal condition
  (a CPU-only stack, a container with no device reserved) and not an error the control API should
  turn into a 503. Fail-closed lives on the brain's side, where a swap that required a fit refuses
  when the answer is ``None``.
- **More than one visible device is also "no reading".** The stack reserves one GPU (ADR-0012) and
  everything downstream compares a single free figure against a single model's cost. Picking a row
  out of several would be a guess about placement that nothing in this repo makes, so the honest
  answer is that this seam does not know, logged where an operator will see it.
- **Bounded.** The call runs inside a swap step on the brain's side, under one control deadline,
  so a hung ``nvidia-smi`` must not hold the request open. The bound is the readiness probe's, both
  being control-plane reads that may never outlive a swap step.
"""

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
                "no device memory reading is available",
                extra={"binary": self._binary, "error": str(err)},
            )
            return None
        if process.returncode != 0:
            _logger.warning(
                "the device memory query exited with a non-zero code",
                extra={"binary": self._binary, "returncode": process.returncode},
            )
            return None
        return stdout.decode(errors="replace")


def _parse(output: str) -> DeviceMemory | None:
    """The one row of two integers, or ``None`` when that is not what came back."""
    rows = [row for row in output.splitlines() if row.strip()]
    if len(rows) != 1:
        _logger.warning(
            "a device memory reading needs exactly one visible GPU", extra={"rows": len(rows)}
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
