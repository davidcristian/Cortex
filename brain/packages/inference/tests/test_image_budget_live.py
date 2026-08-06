"""What one picture costs the cortex, and what the deployment knob that changes it really does.

Three live claims, none of which CI can make, all of them about the resident cortex plus its
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

Integration-marked (excluded from CI and the coverage gate). Needs the GPU, the toolkit, and the
cortex plus its projector at ``CORTEX_MODELS_DIR`` (docs/runbooks/llamacpp-gpu.md):

    cd brain && CORTEX_MODELS_DIR=/srv/models uv run pytest -m integration --no-cov -s \\
        packages/inference/tests/test_image_budget_live.py
"""

import base64
import contextlib
import os
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from rendered_screens import Canvas

from cortex_model_manager import ModelHostConfig

# The sidecar's OWN image, not the base tag the injection harness runs, because two of the three
# claims below are properties of a particular llama.cpp build and the base tag drifts under you:
# a locally cached `server-cuda` and the model-host image built from it were four hundred builds
# apart on the machine this was written on, and they disagreed about the abort in the third arm.
# Build it with `docker compose --project-directory . -f docker/docker-compose.yml
# -f docker/docker-compose.gpu.yml build model-host`.
_IMAGE = os.environ.get("CORTEX_LLAMA_IMAGE", "cortex-model-host")
_MODELS_DIR = os.environ.get("CORTEX_MODELS_DIR", "/srv/models")
_PORT = 8080
_ENDPOINT = f"http://127.0.0.1:{_PORT}/v1/chat/completions"
_HEALTH = f"http://127.0.0.1:{_PORT}/health"
_HEALTH_TIMEOUT_S = 180
_CONTAINER = "cortex-budget-probe"

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
    monkeypatch.setenv("CORTEX_MMPROJ_FILE_CORTEX", _MMPROJ)
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
    deadline = time.monotonic() + _HEALTH_TIMEOUT_S
    while time.monotonic() < deadline:
        with contextlib.suppress(httpx.HTTPError):
            if httpx.get(_HEALTH, timeout=2).status_code == 200:
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
    resp = httpx.post(_ENDPOINT, json=body, timeout=300)
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
