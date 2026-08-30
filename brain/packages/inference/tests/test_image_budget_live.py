"""What one picture costs the cortex, what the knob that changes it does, and what it can read.

Four live claims, none of which CI can make, all of them about the resident cortex plus its
projector on a real card (ADR-0029's legibility measurement):

1. The model declares its own per-image token budget and **saturates** at it, so past a certain
   size a bigger capture buys nothing. That number is what makes a 4K desktop's interface text
   unreadable, and it is the premise the whole region-capture deferral rests on. It is what a
   deployment falls back to when it turns ``CORTEX_IMAGE_MAX_TOKENS`` off.
2. ``CORTEX_IMAGE_MAX_TOKENS`` raises it, which is why it defaults to 1024. The argv under test is
   built by the shipped ``ModelHostConfig``, not typed here, so this measures the knob and not a
   flag.
3. Raising llama.cpp's ``--image-max-tokens`` **without** the matching ``--ubatch-size`` aborts
   the server on the first oversized picture. That is why the knob emits the pair, and this arm
   is the proof the coupling is load-bearing rather than defensive.
4. A capture pointed at **one window** reads text a whole shrunk desktop loses, or it does not.
   The budget above buys pixels per picture; a crop buys pixels per thing the user asked about,
   and the two are the numerator and the denominator of the same ratio. That arm renders its
   own corpus ([desktop_corpus.py](desktop_corpus.py)), runs the whole-display arm beside the
   crop as its control, and prints a table rather than gating on a number.

Integration-marked (excluded from CI and the coverage gate). Needs the GPU, the toolkit, and the
cortex plus its projector at ``CORTEX_MODELS_DIR`` (docs/runbooks/llamacpp-gpu.md):

    cd brain && CORTEX_MODELS_DIR=/srv/models uv run pytest -m integration --no-cov -s \\
        packages/inference/tests/test_image_budget_live.py
"""

import base64
import contextlib
import json
import os
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from desktop_corpus import desktops
from rendered_screens import Canvas
from window_crop_probe import (
    ARMS,
    Reading,
    messages,
    picture,
    readings,
    report,
    schema,
    tally,
)

from cortex_core import CaptureTarget
from cortex_model_manager import ModelHostConfig
from cortex_orchestrator.config_body import BodyConfig

# The sidecar's OWN image, not the base tag the injection harness runs, because two of the three
# claims below are properties of a particular llama.cpp build and the base tag drifts under you:
# a locally cached `server-cuda` and the model-host image built from it were four hundred builds
# apart on the machine this was written on, and they disagreed about the abort in the third arm.
# Build it with `docker compose --project-directory . -f docker/docker-compose.yml
# -f docker/docker-compose.gpu.yml build model-host`.
_IMAGE = os.environ.get("CORTEX_LLAMA_IMAGE", "cortex-model-host")
_MODELS_DIR = os.environ.get("CORTEX_MODELS_DIR", "/srv/models")
_PORT = 8080
_HEALTH_TIMEOUT_S = 180
_CONTAINER = "cortex-budget-probe"

# Where the probe answers. The published loopback port is the documented path and the default,
# but it is not reachable under every WSL networking mode: with mirrored networking a connection
# to 127.0.0.1 is routed to the Windows host, where the Linux docker-proxy is not listening, and
# the whole run then fails as an unhealthy server. ``CORTEX_PROBE_HOST=container`` asks the
# daemon where the container is instead; any other value is used verbatim.
_CONTAINER_ADDRESS = "container"
_PROBE_HOST = os.environ.get("CORTEX_PROBE_HOST", "127.0.0.1")
_ADDRESS_FORMAT = "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"


def _base_url() -> str:
    """The probe's base URL, resolved when it is needed rather than at import."""
    if _PROBE_HOST != _CONTAINER_ADDRESS:
        return f"http://{_PROBE_HOST}:{_PORT}"
    address = subprocess.run(  # noqa: S603
        ["docker", "inspect", "-f", _ADDRESS_FORMAT, _CONTAINER],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return f"http://{address.stdout.strip()}:{_PORT}"


# The cortex pick and its projector, the pair docker/docker-compose.gpu.yml names by default.
_CORTEX = "google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf"
_MMPROJ = "google/gemma-4-12B-it-qat-q4_0-gguf/mmproj-gemma-4-12b-it-qat-q4_0.gguf"

# A whole 4K desktop, which is what the capture path is bounded for. Flat colour and a little
# text: this arm counts tokens and watches for a crash, so what the picture *says* is irrelevant
# and a cheap one keeps the encode inside a test's patience.
_SOURCE = (3840, 2160)

# llama.cpp's own micro-batch default. A budget above it needs --ubatch-size or the decode aborts.
_ENGINE_UBATCH = 512


def _screen() -> bytes:
    canvas = Canvas(_SOURCE[0], _SOURCE[1], (18, 18, 24))
    canvas.rect(0, 0, _SOURCE[0], 60, (48, 48, 64))
    canvas.text(40, 20, "CORTEX BUDGET PROBE", scale=3, colour=(220, 220, 230))
    for row in range(40):
        line = f"LINE {row:02d} THE QUICK BROWN FOX 0123456789"
        canvas.text(40, 120 + row * 30, line, scale=2, colour=(180, 180, 190))
    return canvas.png()


def _argv_tail(budget: int, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The cortex tier's own argv, minus the binary, exactly as the sidecar would spawn it."""
    monkeypatch.setenv("CORTEX_MODELHOST_MODELS_ROOT", "/models")
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX", _CORTEX)
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", _MMPROJ)
    monkeypatch.setenv("CORTEX_IMAGE_MAX_TOKENS", str(budget))
    monkeypatch.setenv("CORTEX_CTX_SIZE", "16384")
    return list(ModelHostConfig().roster()["cortex"].argv[1:])


def _run_argv(args: list[str]) -> list[str]:
    """The whole ``docker run`` command line for one probe server."""
    return [
        "docker", "run", "-d", "--name", _CONTAINER, "--gpus", "all",
        "-p", f"127.0.0.1:{_PORT}:{_PORT}", "-v", f"{_MODELS_DIR}:/models:ro",
        "--entrypoint", "/app/llama-server", _IMAGE, *args,
    ]  # fmt: skip


@contextmanager
def _server(args: list[str]) -> Generator[None, None, None]:
    subprocess.run(["docker", "rm", "-f", _CONTAINER], capture_output=True, check=False)  # noqa: S603, S607
    subprocess.run(  # noqa: S603
        _run_argv(args),
        capture_output=True,
        check=True,
    )
    try:
        _await_health()
        yield
    finally:
        subprocess.run(["docker", "rm", "-f", _CONTAINER], capture_output=True, check=False)  # noqa: S603, S607


def _await_health() -> None:
    health = f"{_base_url()}/health"
    deadline = time.monotonic() + _HEALTH_TIMEOUT_S
    while time.monotonic() < deadline:
        with contextlib.suppress(httpx.HTTPError):
            if httpx.get(health, timeout=2).status_code == 200:
                return
        time.sleep(2)
    pytest.fail(f"llama-server did not become healthy in {_HEALTH_TIMEOUT_S}s")


def _alive(*, settle_s: float = 15.0) -> bool:
    """Whether the server is still up, given a moment to fall over.

    Polled rather than asked once: an abort unwinds through ``ggml_abort``'s backtrace before
    the process leaves, so a single ``docker inspect`` straight after the failed request answers
    "running" for a container that is already dying. That read cost this arm a false pass.
    """
    deadline = time.monotonic() + settle_s
    while True:
        out = subprocess.run(  # noqa: S603
            ["docker", "inspect", "-f", "{{.State.Running}}", _CONTAINER],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if out.stdout.strip() != "true":
            return False
        if time.monotonic() >= deadline:
            return True
        time.sleep(1)


def _cost(png: bytes) -> int:
    """The prompt tokens one picture adds, measured against the same ask with no picture."""
    ask = "Reply with the single word OK."
    bare = _prompt_tokens([{"role": "user", "content": ask}])
    parts: list[dict[str, object]] = [
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()},
        },
        {"type": "text", "text": ask},
    ]
    return _prompt_tokens([{"role": "user", "content": parts}]) - bare


def _prompt_tokens(messages: list[dict[str, object]]) -> int:
    body: dict[str, object] = {
        "model": "m",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 4,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    resp = httpx.post(f"{_base_url()}/v1/chat/completions", json=body, timeout=300)
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    return int(data["usage"]["prompt_tokens"])


@pytest.mark.integration
def test_the_models_own_budget_saturates_and_the_knob_raises_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 4K screen costs the model's declared budget; the knob buys real resolution back."""
    png = _screen()
    with _server(_argv_tail(0, monkeypatch)):
        declared = _cost(png)
    print(f"\n  CORTEX_IMAGE_MAX_TOKENS=0: {declared} prompt tokens for one 4K screen")  # noqa: T201
    # The premise of the region-capture deferral, and the reason the knob had to be raised: left
    # to itself the model throws a 4K desktop away inside the encoder. It is also why turning the
    # knob off is safe on its own, since a budget this small cannot meet the micro-batch assert
    # the arm below provokes.
    assert declared < _ENGINE_UBATCH

    with _server(_argv_tail(1024, monkeypatch)):
        raised = _cost(png)
        assert _alive(), "the raised budget aborted the server on a 4K picture"
    print(f"  CORTEX_IMAGE_MAX_TOKENS=1024 (the default): {raised} tokens, same screen")  # noqa: T201
    assert raised > 2 * declared, (
        f"the knob bought no resolution: {declared} tokens off against {raised} raised. "
        "Either llama.cpp stopped honouring --image-max-tokens for this model, or the model's "
        "own declared budget rose above the knob."
    )


@pytest.mark.integration
async def test_a_window_crop_reads_what_a_shrunk_desktop_cannot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whether pointing a capture at one window reaches the text a whole 4K screen loses.

    The residue the window target was built for: 15 px type on an unscaled monitor stayed at
    4 of 16 at every image budget measured, because the binding quantity is source pixels per
    image token and the budget only moves the divisor. A window inside the capture edge takes
    the identity arm of the body's ``downscale`` and crosses at full resolution, which is the
    only thing left that moves the numerator.

    Both arms run here, against one corpus, in one session, on one server: the recorded
    whole-display numbers were measured on a corpus that no longer exists, so the control is
    re-run rather than cited. This prints its table and asserts only what is true by
    construction; the reading itself is a measurement and is published whatever it says.
    """
    edge = BodyConfig().capture_max_edge
    corpus = desktops()
    results: dict[str, list[Reading]] = {arm.name: [] for arm in ARMS}
    with _server(_argv_tail(ModelHostConfig().cortex_image_max_tokens, monkeypatch)):
        for desktop in corpus:
            for arm in ARMS:
                shot = picture(desktop, arm, edge)
                if arm.target is CaptureTarget.FOCUS:
                    inside_edge = max(shot.region.width, shot.region.height) <= edge
                    assert shot.resampled is not inside_edge, "the identity arm did not run"
                wire = await messages(desktop, arm, shot)
                answers, tokens = _transcribe(wire, schema(desktop.truths))
                scored = readings(desktop.truths, answers)
                results[arm.name] += scored
                read, wrong, declined = tally(scored)
                print(  # noqa: T201
                    f"  {desktop.name:12s} {arm.name:8s} {shot.width}x{shot.height}"
                    f"{' resampled' if shot.resampled else ' untouched'}"
                    f" {len(shot.png) // 1000:5d} kB {tokens:6d} prompt tokens"
                    f"  read {read:2d}  wrong {wrong:2d}  declined {declined:2d}"
                )
    print(report(results))  # noqa: T201
    assert all(len(scored) == len(results["display"]) for scored in results.values())


def _transcribe(
    wire: list[dict[str, object]], answer_schema: dict[str, object]
) -> tuple[dict[str, Any], int]:
    """Post one vision conversation and read the JSON transcription back off the reply."""
    body: dict[str, object] = {
        "model": "m",
        "messages": wire,
        "temperature": 0,
        "max_tokens": 2048,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_schema", "json_schema": {"schema": answer_schema}},
    }
    resp = httpx.post(f"{_base_url()}/v1/chat/completions", json=body, timeout=1800)
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    content = str(data["choices"][0]["message"]["content"])
    return (json.loads(content), int(data["usage"]["prompt_tokens"]))


@pytest.mark.integration
def test_a_raised_budget_without_the_micro_batch_aborts_the_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Why the knob emits two flags: split them and the process dies, rather than erroring.

    A picture is decoded as one non-causal chunk and llama.cpp asserts the micro-batch is at
    least that large. The failure is a ``GGML_ASSERT`` abort inside ``llama_decode``, so the
    reply never arrives, the server exits, and vision is gone for the rest of the session. If
    this arm ever passes cleanly, llama.cpp has started clamping and the coupling in
    ``ModelHostConfig`` can be revisited.
    """
    whole = _argv_tail(1024, monkeypatch)
    assert whole[-2:] == ["--ubatch-size", "1024"]
    args = whole[:-2]
    assert args[-2:] == ["--image-max-tokens", "1024"]
    with _server(args):
        with contextlib.suppress(httpx.HTTPError):
            _cost(_screen())
        assert not _alive(), (
            "llama-server survived an oversized picture with the engine's default micro-batch, "
            "so the flag pairing in ModelHostConfig may no longer be needed"
        )
