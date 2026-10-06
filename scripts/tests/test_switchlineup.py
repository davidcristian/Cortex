import json
from pathlib import Path

import pytest

from switchlineup import EVERY_S, IMAGE, NAME, PICKS, Machine, Pick, Plan, main, serve_command

ASK = "What does each of them pay?"
PLAIN = f"<|turn>system\n<|think|>\n<turn|>\n<|turn>user\n{ASK}<turn|>\n<|turn>model\n"
SHUT = f"<|turn>user\n{ASK}<turn|>\n<|turn>model\n<|channel>thought\n<channel|>"
OPEN = f"<|turn>user\n{ASK}<turn|>\n<|turn>model\n"
E4B = "gemma-4-E4B-qat-q4_0"
CORTEX = "gemma-4-12B-qat-q4_0"


def write_sample(path: Path, outcome: str) -> None:
    """Write a sample whose constrained switch holds or not, its tail agreeing unless refused."""
    holds = outcome == "holds"
    tail = SHUT if holds != (outcome == "refused") else OPEN
    cells = [
        {"shape": shape, "constrained": shape == "envelope", "switch": switch, "draws": 5}
        | {"deliberated": 0 if switch and (holds or shape == "plain") else 5}
        for shape in ("plain", "envelope")
        for switch in (False, True)
    ]
    sample = {
        "model": path.stem,
        "endpoint": "http://127.0.0.1:8091",
        "build_info": "b11429-d81235049",
        "model_path": "/models/a.gguf",
        "n_ctx": 8192,
        "cap": 256,
        "ask": ASK,
        "renderings": [{"switch": False, "prompt": PLAIN}, {"switch": True, "prompt": tail}],
        "cells": cells,
    }
    path.write_text(json.dumps(sample), encoding="utf-8")


class FakeHost:
    """A machine whose docker, health answers and probe results are scripted."""

    def __init__(
        self,
        *,
        starts: bool = True,
        health: list[bool] | None = None,
        running: bool = True,
        outcomes: dict[str, str | None] | None = None,
    ) -> None:
        self.starts = starts
        self.health = health if health is not None else [True]
        self.alive = running
        self.outcomes = outcomes or {}
        self.commands: list[list[str]] = []
        self.probed: list[str] = []
        self.removed = 0
        self.paused: list[float] = []
        self.said: list[str] = []

    def start(self, command: list[str]) -> bool:
        self.commands.append(command)
        return self.starts

    def healthy(self, port: int) -> bool:
        assert port == 8091
        return self.health.pop(0) if len(self.health) > 1 else self.health[0]

    def running(self) -> bool:
        return self.alive

    def probe(self, pick: Pick, plan: Plan) -> int:
        self.probed.append(pick.name)
        outcome = self.outcomes.get(pick.name, "holds")
        if outcome is None:
            return 1
        write_sample(plan.out / f"switch-{pick.name}.json", outcome)
        return 0

    def remove(self) -> None:
        self.removed += 1

    def pause(self, seconds: float) -> None:
        self.paused.append(seconds)

    def say(self, line: str) -> None:
        self.said.append(line)


@pytest.fixture(autouse=True)
def models(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("CORTEX_MODELS_DIR", str(tmp_path / "models"))
    return tmp_path / "models"


def plan(tmp_path: Path, cpuset: str | None = None) -> Plan:
    return Plan(IMAGE, 8091, tmp_path / "models", tmp_path, cpuset)


def by_name(name: str) -> Pick:
    return next(pick for pick in PICKS if pick.name == name)


def test_a_card_pick_is_served_whole_on_the_card_with_neither_reasoning_flag(
    tmp_path: Path,
) -> None:
    command = serve_command(by_name(CORTEX), plan(tmp_path, cpuset="12-23"))
    assert command[:5] == ["docker", "run", "-d", "--name", NAME]
    assert command[command.index("--gpus") + 1] == "all"
    assert command[command.index("-ngl") + 1] == "99"
    assert "--cpuset-cpus" not in command
    assert command[command.index("--model") + 1] == f"/models/{by_name(CORTEX).path}"
    assert f"{tmp_path / 'models'}:/models:ro" in command
    assert not [arg for arg in command if arg.startswith("--reasoning")]


def test_a_cpu_pick_gets_the_cores_asked_for_and_no_card(tmp_path: Path) -> None:
    pinned = serve_command(by_name(E4B), plan(tmp_path, cpuset="12-23"))
    assert pinned[pinned.index("--cpuset-cpus") + 1] == "12-23"
    assert "--gpus" not in pinned
    assert pinned[pinned.index("-ngl") + 1] == "0"
    loose = serve_command(by_name(E4B), plan(tmp_path))
    assert "--gpus" not in loose
    assert "--cpuset-cpus" not in loose


def test_every_pick_asked_for_is_drawn_and_published(
    models: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = FakeHost(outcomes={E4B: "nothing"})
    code = main(["--only", CORTEX, "--only", E4B, "--out", str(tmp_path / "out")], host)
    assert code == 0
    assert host.probed == [CORTEX, E4B]
    assert host.removed == 4
    assert [c[c.index("--model") + 1] for c in host.commands] == [
        f"/models/{by_name(CORTEX).path}",
        f"/models/{by_name(E4B).path}",
    ]
    assert all(f"{models}:/models:ro" in c for c in host.commands)
    assert capsys.readouterr().out.count("agreed:") == 2


def test_a_server_is_waited_on_until_it_answers(tmp_path: Path) -> None:
    host = FakeHost(health=[False, False, True])
    assert main(["--only", CORTEX, "--out", str(tmp_path)], host) == 0
    assert host.paused == [EVERY_S, EVERY_S]
    assert host.probed == [CORTEX]


@pytest.mark.parametrize(
    ("host", "pauses"),
    [
        (FakeHost(starts=False), 0),
        (FakeHost(health=[False], running=False), 0),
        (FakeHost(health=[False]), 120),
    ],
    ids=["docker-run-failed", "server-exited", "never-answered"],
)
def test_a_pick_whose_server_never_answers_is_named_and_fails_the_run(
    tmp_path: Path, host: FakeHost, pauses: int
) -> None:
    assert main(["--only", CORTEX, "--out", str(tmp_path)], host) == 1
    assert host.probed == []
    assert len(host.paused) == pauses
    assert host.removed == 2
    assert f"PICK FAILED {CORTEX}: the server never answered /health" in host.said
    assert f"no sample from {CORTEX}" in host.said


def test_a_sample_left_by_an_earlier_run_is_not_published(tmp_path: Path) -> None:
    stale = tmp_path / f"switch-{CORTEX}.json"
    write_sample(stale, "holds")
    host = FakeHost(outcomes={CORTEX: None})
    assert main(["--only", CORTEX, "--out", str(tmp_path)], host) == 1
    assert not stale.exists()
    assert f"PICK END {CORTEX}: the probe exited 1" in host.said


def test_one_pick_with_no_sample_fails_a_run_the_reader_agrees_with(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = FakeHost(outcomes={E4B: None})
    assert main(["--only", CORTEX, "--only", E4B, "--out", str(tmp_path)], host) == 1
    assert "agreed:" in capsys.readouterr().out
    assert f"no sample from {E4B}" in host.said


def test_a_row_the_reader_refuses_fails_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = FakeHost(outcomes={CORTEX: "refused"})
    assert main(["--only", CORTEX, "--out", str(tmp_path)], host) == 1
    assert "refused:" in capsys.readouterr().out


def test_a_pick_not_in_the_lineup_is_refused_before_anything_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = FakeHost()
    assert main(["--only", "gemma-9", "--out", str(tmp_path)], host) == 2
    assert "no pick named gemma-9" in capsys.readouterr().err
    assert host.commands == []


def test_a_run_with_no_models_directory_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("CORTEX_MODELS_DIR", raising=False)
    host = FakeHost()
    assert main(["--out", str(tmp_path)], host) == 2
    assert "CORTEX_MODELS_DIR is unset" in capsys.readouterr().err
    assert host.commands == []


def test_every_pick_in_the_lineup_is_drawn_when_none_is_named(tmp_path: Path) -> None:
    host = FakeHost()
    main(["--out", str(tmp_path)], host)
    assert host.probed == [pick.name for pick in PICKS]


def test_the_real_host_prints_each_line_after_the_clock(
    capsys: pytest.CaptureFixture[str],
) -> None:
    Machine().pause(0.0)
    Machine().say("PICK x")
    assert capsys.readouterr().out.endswith(" PICK x\n")
