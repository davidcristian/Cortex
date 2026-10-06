"""Draw the thinking-switch lineup on one engine image and publish every row through switchtail."""

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple, Protocol, cast

import switchtail

NAME = "cortex-switch-lineup"
IMAGE = "cortex-model-host"
PORT = 8091
TRIES = 120
EVERY_S = 5.0
PROBE_S = 900
REPEATS = 5
PROBE = "packages/inference/tests/test_thinking_switch_live.py"
OUT = Path("measurements/switch-lineup")


class Pick(NamedTuple):
    """One row of the rendering column: the probe's model name, its file and its GPU layers."""

    name: str
    path: str
    ngl: int


# The rows of the rendering column in docs/readings/thinking-switch.md. The E4B is served on the
# CPU, where its row was first read.
PICKS: tuple[Pick, ...] = (
    Pick(
        "gemma-4-12B-qat-q4_0",
        "google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf",
        99,
    ),
    Pick("gemma-4-E4B-qat-q4_0", "google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf", 0),
    Pick(
        "gemma-4-31B-qat-q4_0", "google/gemma-4-31B-it-qat-q4_0-gguf/gemma-4-31B_q4_0-it.gguf", 99
    ),
    Pick("Qwen3.5-2B-Q4_K_M", "unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q4_K_M.gguf", 99),
    Pick("Qwen3.8-27B-UD-Q4_K_M", "unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf", 99),
    Pick(
        "gemma-4-E2B-qat-q4_0", "google/gemma-4-E2B-it-qat-q4_0-gguf/gemma-4-E2B_q4_0-it.gguf", 99
    ),
    Pick("Qwen3.5-0.8B-Q8_0", "unsloth/Qwen3.5-0.8B-GGUF/Qwen3.5-0.8B-Q8_0.gguf", 99),
    Pick("Qwen3.5-4B-Q4_K_M", "unsloth/Qwen3.5-4B-GGUF/Qwen3.5-4B-Q4_K_M.gguf", 99),
    Pick("Qwen3.5-9B-UD-Q4_K_XL", "unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-UD-Q4_K_XL.gguf", 99),
    Pick(
        "gemma-4-26B-A4B-qat-q4_0",
        "google/gemma-4-26B-A4B-it-qat-q4_0-gguf/gemma-4-26B_q4_0-it.gguf",
        99,
    ),
    Pick("Qwen3.6-27B-Q4_K_M", "unsloth/Qwen3.6-27B-GGUF/Qwen3.6-27B-Q4_K_M.gguf", 99),
    Pick(
        "Qwen3.6-35B-A3B-UD-Q3_K_XL",
        "unsloth/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf",
        99,
    ),
)


class Plan(NamedTuple):
    """Where the servers run and where their samples go, the same for every pick."""

    image: str
    port: int
    models: Path
    out: Path
    cpuset: str | None
    tries: int = TRIES
    every: float = EVERY_S


class Host(Protocol):
    """What the loop does to the machine, so a test can hand it a fake one."""

    def start(self, command: list[str]) -> bool: ...
    def healthy(self, port: int) -> bool: ...
    def running(self) -> bool: ...
    def probe(self, pick: Pick, plan: Plan) -> int: ...
    def remove(self) -> None: ...
    def pause(self, seconds: float) -> None: ...
    def say(self, line: str) -> None: ...


def serve_command(pick: Pick, plan: Plan) -> list[str]:
    """The `docker run` that serves one pick with neither reasoning flag."""
    place = ["--gpus", "all"] if pick.ngl > 0 else []
    if pick.ngl == 0 and plan.cpuset:
        place = ["--cpuset-cpus", plan.cpuset]
    return [
        *("docker", "run", "-d", "--name", NAME, *place),
        *("-p", f"127.0.0.1:{plan.port}:8080", "-v", f"{plan.models}:/models:ro"),
        *("--entrypoint", "/app/llama-server", plan.image, "--model", f"/models/{pick.path}"),
        *("--host", "0.0.0.0", "--port", "8080", "-ngl", str(pick.ngl)),  # noqa: S104 -- in the container
        *("--ctx-size", "8192", "--parallel", "1", "--jinja", "--cache-ram", "0"),
    ]


def serve(pick: Pick, plan: Plan, host: Host) -> bool:
    """Start one pick's server and wait until it answers `/health` or stops running."""
    if not host.start(serve_command(pick, plan)):
        return False
    for _ in range(plan.tries):
        if host.healthy(plan.port):
            return True
        if not host.running():
            return False
        host.pause(plan.every)
    return False


def lineup(picks: Iterable[Pick], plan: Plan, host: Host) -> tuple[list[Path], list[str]]:
    """Draw each pick in turn; return the samples written and the picks that wrote none."""
    written: list[Path] = []
    missed: list[str] = []
    for pick in picks:
        sample = plan.out / f"switch-{pick.name}.json"
        sample.unlink(missing_ok=True)
        host.remove()
        host.say(f"PICK {pick.name} at -ngl {pick.ngl}")
        if serve(pick, plan, host):
            host.say(f"PICK END {pick.name}: the probe exited {host.probe(pick, plan)}")
        else:
            host.say(f"PICK FAILED {pick.name}: the server never answered /health")
        host.remove()
        if sample.is_file():
            written.append(sample)
        else:
            missed.append(pick.name)
    return written, missed


class Machine:
    """The real host: its docker, the brain's probe, its clock and its standard output."""

    def start(self, command: list[str]) -> bool:  # pragma: no cover -- needs a real docker
        """Run the `docker run` command and say whether docker started the container."""
        result = subprocess.run(command, capture_output=True, check=False, text=True)  # noqa: S603
        if result.returncode != 0:
            self.say(result.stderr.strip())
        return result.returncode == 0

    def healthy(self, port: int) -> bool:  # pragma: no cover -- needs a real server
        """Whether the server on ``port`` answers `/health` with a 200."""
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=10) as reply:
                return cast("int", reply.status) == 200  # noqa: PLR2004
        except OSError:
            return False

    def running(self) -> bool:  # pragma: no cover -- needs a real docker
        """Whether the container is still running."""
        result = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["docker", "inspect", "--format", "{{.State.Running}}", NAME],  # noqa: S607
            capture_output=True,
            check=False,
            text=True,
        )
        return result.stdout.strip() == "true"

    def probe(self, pick: Pick, plan: Plan) -> int:  # pragma: no cover -- needs a real server
        """Run the brain's switch probe against the server, and return its exit code."""
        env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"} | {
            "CORTEX_THINKING_ENDPOINT": f"http://127.0.0.1:{plan.port}",
            "CORTEX_THINKING_MODEL": pick.name,
            "CORTEX_THINKING_REPEATS": str(REPEATS),
            "CORTEX_THINKING_OUT": str(plan.out.resolve()),
        }
        command = ["uv", "run", "pytest", "-m", "integration", "--no-cov", "-s", PROBE]
        try:
            done = subprocess.run(command, cwd="brain", env=env, check=False, timeout=PROBE_S)  # noqa: S603
        except subprocess.TimeoutExpired:
            return 124
        return done.returncode

    def remove(self) -> None:  # pragma: no cover -- needs a real docker
        """Kill and remove the container, if there is one."""
        subprocess.run(["docker", "rm", "--force", NAME], capture_output=True, check=False)  # noqa: S603, S607

    def pause(self, seconds: float) -> None:
        """Sleep for ``seconds``."""
        time.sleep(seconds)

    def say(self, line: str) -> None:
        """Print one log line with the wall-clock time in front."""
        print(f"{time.strftime('%H:%M:%S')} {line}", flush=True)


def main(argv: list[str], host: Host) -> int:
    """Draw the picks asked for and publish them; exit 1 when a pick wrote no sample."""
    parser = argparse.ArgumentParser(description="Draw the thinking-switch lineup on one image.")
    parser.add_argument("--only", action="append", default=[], help="draw only this pick")
    parser.add_argument("--image", default=IMAGE, help="the image whose llama-server serves")
    parser.add_argument("--port", type=int, default=PORT, help="the host port to publish")
    parser.add_argument("--out", type=Path, default=OUT, help="where the samples are written")
    parser.add_argument("--cpuset", default=None, help="CPU cores for the picks served on CPU")
    args = parser.parse_args(argv)
    only = cast("list[str]", args.only)
    unknown = sorted(set(only) - {pick.name for pick in PICKS})
    models = os.environ.get("CORTEX_MODELS_DIR", "")
    if unknown or not models:
        problem = f"no pick named {', '.join(unknown)}" if unknown else "CORTEX_MODELS_DIR is unset"
        print(f"switchlineup: {problem}", file=sys.stderr)
        return 2
    out = cast("Path", args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = Plan(cast("str", args.image), cast("int", args.port), Path(models), out, args.cpuset)
    written, missed = lineup([p for p in PICKS if not only or p.name in only], plan, host)
    if missed:
        host.say(f"no sample from {', '.join(missed)}")
    if not written:
        return 1
    return max(switchtail.main([str(path) for path in written]), 1 if missed else 0)


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main(sys.argv[1:], Machine()))
