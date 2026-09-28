import re
import subprocess
from pathlib import Path

import pytest

from memwatch import (
    FLOOR_MIB,
    FULL_LIMIT,
    LATE_LIMIT_S,
    LEFT_ALONE,
    REMOVED,
    Limits,
    Machine,
    Reading,
    ReadingError,
    available_mib,
    breach,
    full10,
    main,
    watch,
)

# Both texts are copied from this kernel's own files, with the figures changed.
MEMINFO = "MemTotal:       32864276 kB\nMemFree:        10457632 kB\nMemAvailable:   {kib} kB\n"
PRESSURE = (
    "some avg10=0.00 avg60=0.00 avg300=0.00 total=1406746\n"
    "full avg10={full} avg60=0.00 avg300=0.00 total=1390037\n"
)
LIMITS = Limits(floor_mib=2048.0, full_limit=50.0, late_limit_s=2.0)
CALM = (8192 * 1024, "0.00", 0.0)


class FakeHost:
    """A machine whose readings, container states and pause overshoots are scripted in order."""

    def __init__(
        self,
        readings: list[tuple[int, str, float]],
        states: list[str | None] | None = None,
        broken: Exception | None = None,
    ) -> None:
        self.readings = readings
        self.states = states if states is not None else ["running"] * (len(readings) + 1)
        self.broken = broken
        self.lines: list[str] = []
        self.removed: list[str] = []
        self.paused: list[float] = []
        self._at = 0

    def meminfo(self) -> str:
        if self.broken is not None:
            raise self.broken
        return MEMINFO.format(kib=self.readings[self._at][0])

    def pressure(self) -> str:
        return PRESSURE.format(full=self.readings[self._at][1])

    def state(self, name: str) -> str | None:
        assert name == "flash-p2"
        return self.states[self._at]

    def remove(self, name: str) -> None:
        self.removed.append(name)

    def pause(self, seconds: float) -> float:
        self.paused.append(seconds)
        overshoot = self.readings[self._at][2]
        self._at += 1
        return overshoot

    def say(self, line: str) -> None:
        self.lines.append(line)


def test_the_available_figure_is_read_in_mib() -> None:
    assert available_mib(MEMINFO.format(kib=19519752)) == pytest.approx(19062.26, abs=0.01)


@pytest.mark.parametrize(
    "text",
    [
        "MemTotal:       32864276 kB\n",
        "MemAvailable:   19519752 MB\n",
        "MemAvailable:   many kB\n",
        "MemAvailable:\n",
        "",
    ],
)
def test_a_meminfo_without_a_usable_available_figure_is_refused(text: str) -> None:
    with pytest.raises(ReadingError, match="MemAvailable"):
        available_mib(text)


def test_the_full_share_is_read_from_the_full_line_and_not_the_some_line() -> None:
    text = "some avg10=71.25 avg60=0.00\nfull avg10=26.50 avg60=10.50 avg300=0.00 total=9\n"
    assert full10(text) == 26.5


@pytest.mark.parametrize(
    "text",
    [
        "some avg10=26.50 avg60=0.00 avg300=0.00 total=1\n",
        "\nfull avg60=10.50 avg300=0.00 total=1\n",
        "full avg10=high avg60=0.00\n",
        "",
    ],
)
def test_a_pressure_file_without_a_full_ten_second_share_is_refused(text: str) -> None:
    with pytest.raises(ReadingError, match="full avg10"):
        full10(text)


@pytest.mark.parametrize(
    ("reading", "reason"),
    [
        (Reading(2047.0, 0.0, 0.0), "MemAvailable 2047 MiB is under 2048"),
        (Reading(24000.0, 50.01, 0.0), "the memory full share 50.01 is over 50.00"),
        (Reading(24000.0, 0.0, 2.01), "the watchdog woke 2.01 s late, over 2.00"),
    ],
)
def test_each_limit_stops_the_container_on_one_reading(reading: Reading, reason: str) -> None:
    assert breach(reading, LIMITS) == reason


def test_the_readings_of_a_row_that_harmed_nothing_cross_no_limit() -> None:
    assert breach(Reading(24000.0, 26.5, 0.0), LIMITS) is None
    assert breach(Reading(2048.0, 50.0, 2.0), LIMITS) is None


def test_a_calm_host_is_read_until_the_container_leaves_on_its_own() -> None:
    host = FakeHost([CALM, CALM], states=["running", "running", None])
    assert watch("flash-p2", LIMITS, 1.5, host) == LEFT_ALONE
    assert host.removed == []
    assert host.paused == [1.5, 1.5]
    assert host.lines[1:] == [
        "avail 8192 MiB, full10 0.00, late 0.00 s",
        "avail 8192 MiB, full10 0.00, late 0.00 s",
        "flash-p2 is gone; the watchdog exits",
    ]


def test_a_container_the_kernel_ended_is_reported_and_left_alone() -> None:
    host = FakeHost([CALM], states=["running", "exited oom=true exit=137"])
    assert watch("flash-p2", LIMITS, 1.0, host) == LEFT_ALONE
    assert host.removed == []
    assert host.lines[-1] == "flash-p2 ended without the watchdog: exited oom=true exit=137"


def test_falling_available_memory_removes_the_container_at_the_first_reading_under_the_floor() -> (
    None
):
    host = FakeHost([CALM, (3000 * 1024, "4.00", 0.0), (2000 * 1024, "9.00", 0.0), CALM])
    assert watch("flash-p2", LIMITS, 1.0, host) == REMOVED
    assert host.removed == ["flash-p2"]
    assert host.lines[-2:] == [
        "STOP flash-p2: MemAvailable 2000 MiB is under 2048",
        "removed flash-p2",
    ]


def test_a_late_wake_is_charged_to_the_reading_after_the_pause_that_overshot() -> None:
    host = FakeHost([(8192 * 1024, "0.00", 2.5), CALM])
    assert watch("flash-p2", LIMITS, 1.0, host) == REMOVED
    assert host.lines[-3] == "avail 8192 MiB, full10 0.00, late 2.50 s"
    assert host.lines[-2] == "STOP flash-p2: the watchdog woke 2.50 s late, over 2.00"


def test_a_host_that_cannot_be_read_stops_the_container_rather_than_leave_it_unwatched() -> None:
    host = FakeHost([CALM], broken=FileNotFoundError("/proc/pressure/memory"))
    assert watch("flash-p2", LIMITS, 1.0, host) == REMOVED
    assert host.removed == ["flash-p2"]
    assert host.lines[-2] == "STOP flash-p2: the host cannot be read: /proc/pressure/memory"


def test_a_gone_container_is_never_read_or_removed() -> None:
    host = FakeHost([], states=[None], broken=AssertionError("read"))
    assert watch("flash-p2", LIMITS, 1.0, host) == LEFT_ALONE
    assert host.removed == []


def test_the_command_line_sets_each_limit() -> None:
    host = FakeHost([(3000 * 1024, "0.00", 0.0)])
    argv = ["flash-p2", "--floor-mib", "4096", "--full-limit", "5", "--late-limit", "1"]
    assert main([*argv, "--every", "0.5"], host) == REMOVED
    assert host.lines[0] == (
        "watching flash-p2: floor 4096 MiB, full10 limit 5.00, late limit 1.00 s, every 0.50 s"
    )


def test_the_command_line_defaults_are_the_documented_limits() -> None:
    host = FakeHost([], states=[None])
    assert main(["flash-p2"], host) == LEFT_ALONE
    assert host.lines[0] == (
        f"watching flash-p2: floor {FLOOR_MIB:.0f} MiB, full10 limit {FULL_LIMIT:.2f},"
        f" late limit {LATE_LIMIT_S:.2f} s, every 1.00 s"
    )


def test_the_machine_reads_the_two_files_it_was_given(tmp_path: Path) -> None:
    meminfo, pressure = tmp_path / "meminfo", tmp_path / "memory"
    meminfo.write_text(MEMINFO.format(kib=1024), encoding="ascii")
    pressure.write_text(PRESSURE.format(full="3.25"), encoding="ascii")
    machine = Machine(meminfo, pressure)
    assert available_mib(machine.meminfo()) == 1.0
    assert full10(machine.pressure()) == 3.25


def test_the_machine_reports_no_overshoot_below_zero_and_stamps_each_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    machine = Machine()
    assert machine.pause(0.0) >= 0.0
    machine.say("removed flash-p2")
    assert re.fullmatch(r"\d\d:\d\d:\d\d removed flash-p2\n", capsys.readouterr().out)


@pytest.mark.integration
def test_the_machine_sees_a_real_container_run_and_removes_it() -> None:
    name = "cortex-memwatch-probe"
    started = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        ["docker", "run", "-d", "--rm", "--name", name, "python:3.12-slim", "sleep", "60"],  # noqa: S607
        capture_output=True,
        check=True,
    )
    assert started.returncode == 0
    machine = Machine()
    running = machine.state(name)
    assert running is not None
    assert running.startswith("running")
    machine.remove(name)
    assert machine.state(name) is None
