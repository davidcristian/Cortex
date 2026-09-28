"""Remove a measurement container when the host running it runs short of memory."""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple, Protocol, cast

MEMINFO = Path("/proc/meminfo")
PRESSURE = Path("/proc/pressure/memory")
KIB_PER_MIB = 1024
FLOOR_MIB = 2048.0
# A Flash-Next row under a 20 GiB cap reached 26.5 while the host kept 24,220 MiB available and
# nothing woke late, so a row thrashing inside its own cap stays well under this limit.
FULL_LIMIT = 50.0
LATE_LIMIT_S = 2.0
EVERY_S = 1.0
INSPECT_FORMAT = "{{.State.Status}} oom={{.State.OOMKilled}} exit={{.State.ExitCode}}"
RUNNING = "running"
LEFT_ALONE = 0
REMOVED = 1


class ReadingError(Exception):
    """A file under /proc does not hold the figure the watchdog reads from it."""


class Limits(NamedTuple):
    """The three limits, any one of which a single reading can cross."""

    floor_mib: float
    full_limit: float
    late_limit_s: float


class Reading(NamedTuple):
    """One look at the host: MiB available, the memory full share over 10 s, and lateness."""

    available_mib: float
    full10: float
    late_s: float

    def line(self) -> str:
        """The reading as one log line."""
        return (
            f"avail {self.available_mib:.0f} MiB, full10 {self.full10:.2f},"
            f" late {self.late_s:.2f} s"
        )


class Host(Protocol):
    """What the watchdog reads from and does to the machine, so a test can hand it a fake one."""

    def meminfo(self) -> str: ...
    def pressure(self) -> str: ...
    def state(self, name: str) -> str | None: ...
    def remove(self, name: str) -> None: ...
    def pause(self, seconds: float) -> float: ...
    def say(self, line: str) -> None: ...


def available_mib(meminfo: str) -> float:
    """The `MemAvailable` figure of a /proc/meminfo text, in MiB."""
    for line in meminfo.splitlines():
        key, _, rest = line.partition(":")
        match rest.split():
            case [figure, "kB"] if key == "MemAvailable" and figure.isdigit():
                return int(figure) / KIB_PER_MIB
            case _:
                continue
    msg = "/proc/meminfo has no MemAvailable figure in kB"
    raise ReadingError(msg)


def full10(pressure: str) -> float:
    """The `full avg10` share of a /proc/pressure/memory text, in percent."""
    for line in pressure.splitlines():
        fields = line.split()
        if fields[:1] != ["full"]:
            continue
        for field in fields[1:]:
            key, _, value = field.partition("=")
            if key == "avg10":
                try:
                    return float(value)
                except ValueError:
                    break
    msg = "/proc/pressure/memory has no full avg10 figure"
    raise ReadingError(msg)


def breach(reading: Reading, limits: Limits) -> str | None:
    """Why this reading stops the container, or ``None`` when it crosses no limit."""
    if reading.available_mib < limits.floor_mib:
        return f"MemAvailable {reading.available_mib:.0f} MiB is under {limits.floor_mib:.0f}"
    if reading.full10 > limits.full_limit:
        return f"the memory full share {reading.full10:.2f} is over {limits.full_limit:.2f}"
    if reading.late_s > limits.late_limit_s:
        return f"the watchdog woke {reading.late_s:.2f} s late, over {limits.late_limit_s:.2f}"
    return None


def watch(name: str, limits: Limits, every: float, host: Host) -> int:
    """Read the host every ``every`` seconds until the container ends or a reading stops it."""
    host.say(
        f"watching {name}: floor {limits.floor_mib:.0f} MiB, full10 limit"
        f" {limits.full_limit:.2f}, late limit {limits.late_limit_s:.2f} s, every {every:.2f} s"
    )
    late = 0.0
    while True:
        state = host.state(name)
        if state is None:
            host.say(f"{name} is gone; the watchdog exits")
            return LEFT_ALONE
        if not state.startswith(RUNNING):
            host.say(f"{name} ended without the watchdog: {state}")
            return LEFT_ALONE
        try:
            reading = Reading(available_mib(host.meminfo()), full10(host.pressure()), late)
        except (ReadingError, OSError) as err:
            reason: str | None = f"the host cannot be read: {err}"
        else:
            host.say(reading.line())
            reason = breach(reading, limits)
        if reason is not None:
            host.say(f"STOP {name}: {reason}")
            host.remove(name)
            host.say(f"removed {name}")
            return REMOVED
        late = host.pause(every)


class Machine:
    """The real host: its /proc files, its docker, its clock and its standard output."""

    def __init__(self, meminfo: Path = MEMINFO, pressure: Path = PRESSURE) -> None:
        """Read the two /proc files at the paths given."""
        self._meminfo = meminfo
        self._pressure = pressure

    def meminfo(self) -> str:
        """The current /proc/meminfo text."""
        return self._meminfo.read_text(encoding="ascii")

    def pressure(self) -> str:
        """The current /proc/pressure/memory text."""
        return self._pressure.read_text(encoding="ascii")

    def state(self, name: str) -> str | None:  # pragma: no cover -- needs a real docker
        """The container's status line, or ``None`` when docker has no such container."""
        result = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["docker", "inspect", "--format", INSPECT_FORMAT, name],  # noqa: S607
            capture_output=True,
            check=False,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def remove(self, name: str) -> None:  # pragma: no cover -- needs a real docker
        """Kill and remove the container."""
        subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["docker", "rm", "--force", name],  # noqa: S607
            capture_output=True,
            check=False,
        )

    def pause(self, seconds: float) -> float:
        """Sleep, and return how much longer than ``seconds`` the sleep took."""
        start = time.monotonic()
        time.sleep(seconds)
        return max(0.0, time.monotonic() - start - seconds)

    def say(self, line: str) -> None:
        """Print one log line with the wall-clock time in front."""
        print(f"{time.strftime('%H:%M:%S')} {line}", flush=True)


def main(argv: list[str], host: Host) -> int:
    """Parse the command line and watch; exit 1 when the watchdog removed the container."""
    parser = argparse.ArgumentParser(
        description=(
            "Remove a running container when host MemAvailable falls under a floor, the memory"
            " full share over 10 s rises over a limit, or the watchdog itself wakes late."
        ),
    )
    parser.add_argument("name", help="the container to watch and remove")
    parser.add_argument("--floor-mib", type=float, default=FLOOR_MIB, help="MemAvailable floor")
    parser.add_argument("--full-limit", type=float, default=FULL_LIMIT, help="full avg10 limit")
    parser.add_argument("--late-limit", type=float, default=LATE_LIMIT_S, help="seconds late")
    parser.add_argument("--every", type=float, default=EVERY_S, help="seconds between readings")
    args = parser.parse_args(argv)
    limits = Limits(
        cast("float", args.floor_mib),
        cast("float", args.full_limit),
        cast("float", args.late_limit),
    )
    return watch(cast("str", args.name), limits, cast("float", args.every), host)


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main(sys.argv[1:], Machine()))
