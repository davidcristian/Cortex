import contextlib
import os
import subprocess
import time
from collections.abc import AsyncIterator, Generator, Sequence
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from rendered_screens import Canvas

from cortex_core import (
    MAX_ATTACHED_IMAGES,
    GenerationBounds,
    ImagePart,
    InferenceEvent,
    InMemorySessionStore,
    JsonSchema,
    Message,
    ReasoningChunk,
    SingleResidentModelManager,
    SystemClock,
    TextDelta,
    ToolSpec,
    TurnEngine,
)
from cortex_inference import LlamaCppBackend
from cortex_inference.request import build_payload
from cortex_model_manager import ModelHostConfig

_IMAGE = os.environ.get("CORTEX_LLAMA_IMAGE", "cortex-model-host")
_MODELS_DIR = os.environ.get("CORTEX_MODELS_DIR", "/srv/models")
_CORTEX = "google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf"
_MMPROJ = "google/gemma-4-12B-it-qat-q4_0-gguf/mmproj-gemma-4-12b-it-qat-q4_0.gguf"
_CONTAINER = "cortex-attach-probe"
_PORT = 8080
_HEALTH_TIMEOUT_S = 180
_MODEL = "cortex"
_SAMPLES = 3
# The overlay's ``DEFAULT_MAX_EDGE`` in body/app/src/overlay/pictures.ts, the long edge the body
# downscales an attachment to; the brain's own capture edge is larger.
_EDGE = 1600

# One word per picture, each on its own background, so a reply that names all four shows the
# model read every attachment rather than the first or the last.
_PICTURES = (
    ("HARBOUR", (20, 60, 140)),
    ("LANTERN", (150, 30, 30)),
    ("MEADOW", (30, 110, 40)),
    ("PEBBLE", (90, 90, 90)),
)


def _picture(word: str, background: tuple[int, int, int]) -> ImagePart:
    width, height = _EDGE, _EDGE * 9 // 16
    canvas = Canvas(width, height, background)
    canvas.rect(width // 8, height // 3, width * 3 // 4, height // 3, (245, 245, 240))
    canvas.text(width // 8 + 40, height // 2 - 40, word, scale=14, colour=(10, 10, 10))
    return ImagePart(data=canvas.png(), mime_type="image/png", width=width, height=height)


def _argv(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Return the cortex tier's argv, minus the binary, as the sidecar would spawn it."""
    monkeypatch.setenv("CORTEX_MODELHOST_MODELS_ROOT", "/models")
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX", _CORTEX)
    monkeypatch.setenv("CORTEX_MODEL_FILE_CORTEX_MMPROJ", _MMPROJ)
    return list(ModelHostConfig().roster()["cortex"].argv[1:])


def _base_url() -> str:
    """Return the probe's base URL; ``CORTEX_PROBE_HOST=container`` asks the daemon for it."""
    host = os.environ.get("CORTEX_PROBE_HOST", "127.0.0.1")
    if host == "container":
        fmt = "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"
        out = subprocess.run(  # noqa: S603
            ["docker", "inspect", "-f", fmt, _CONTAINER],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        host = out.stdout.strip()
    return f"http://{host}:{_PORT}"


def _run_argv(args: list[str]) -> list[str]:
    return [
        "docker", "run", "-d", "--name", _CONTAINER, "--gpus", "all",
        "-p", f"127.0.0.1:{_PORT}:{_PORT}", "-v", f"{_MODELS_DIR}:/models:ro",
        "--entrypoint", "/app/llama-server", _IMAGE, *args,
    ]  # fmt: skip


@contextmanager
def _server(args: list[str]) -> Generator[None, None, None]:
    remove = ["docker", "rm", "-f", _CONTAINER]
    subprocess.run(remove, capture_output=True, check=False)  # noqa: S603
    subprocess.run(_run_argv(args), capture_output=True, check=True)  # noqa: S603
    try:
        deadline = time.monotonic() + _HEALTH_TIMEOUT_S
        while time.monotonic() < deadline:
            with contextlib.suppress(httpx.HTTPError):
                if httpx.get(f"{_base_url()}/health", timeout=2).status_code == 200:
                    break
            time.sleep(2)
        else:
            pytest.fail(f"llama-server did not become healthy in {_HEALTH_TIMEOUT_S}s")
        yield
    finally:
        subprocess.run(remove, capture_output=True, check=False)  # noqa: S603


class _Recording:
    """Pass a real backend's events through, keeping what was sent and the reasoning trace."""

    def __init__(self, inner: LlamaCppBackend) -> None:
        self._inner = inner
        self.sent: list[tuple[Message, ...]] = []
        self.reasoning: list[str] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        self.sent.append(tuple(messages))
        async for event in self._inner.stream(
            model, messages, tools=tools, schema=schema, bounds=bounds
        ):
            if isinstance(event, ReasoningChunk):
                self.reasoning.append(event.text)
            yield event


async def _turn(images: tuple[ImagePart, ...], ask: str) -> tuple[str, _Recording]:
    manager = SingleResidentModelManager(_MODEL, _base_url())
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        backend = _Recording(LlamaCppBackend(manager, client))
        engine = TurnEngine(InMemorySessionStore(), backend, SystemClock(), cortex_model=_MODEL)
        parts = [
            event.text
            async for event in engine.handle_turn("live", ask, turn_id="t-1", images=images)
            if isinstance(event, TextDelta)
        ]
    return "".join(parts), backend


def _price(messages: Sequence[Message]) -> tuple[int, float, float]:
    """Post the turn's own messages once, uncached; return prompt tokens, engine ms, wall s."""
    body = build_payload(_MODEL, messages, (), None, GenerationBounds(max_tokens=1))
    body.update(stream=False, cache_prompt=False)
    started = time.perf_counter()
    resp = httpx.post(f"{_base_url()}/v1/chat/completions", json=body, timeout=600)
    wall = time.perf_counter() - started
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    return int(data["usage"]["prompt_tokens"]), float(data["timings"]["prompt_ms"]), wall


def _clock() -> str:
    out = subprocess.run(  # noqa: S603
        [
            os.environ.get("CORTEX_NVIDIA_SMI", "nvidia-smi"),
            "--query-gpu=clocks.sm,clocks.max.sm",
            "--format=csv,noheader",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip() or "unread"


@pytest.mark.integration
async def test_an_attached_picture_reaches_the_cortex_and_four_fit_its_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pictures = tuple(_picture(word, colour) for word, colour in _PICTURES)
    assert len(pictures) == MAX_ATTACHED_IMAGES
    ctx = ModelHostConfig().cortex_ctx_size
    with _server(_argv(monkeypatch)):
        reply, one = await _turn(pictures[:1], "What word is written in this picture?")
        print(f"\n  one picture: {reply!r}, reasoning {len(''.join(one.reasoning))} chars")  # noqa: T201
        assert "HARBOUR" in reply.upper()

        ask = "List the word written in each picture, in order."
        reply, four = await _turn(pictures, ask)
        print(f"  four pictures: {reply!r}, reasoning {len(''.join(four.reasoning))} chars")  # noqa: T201
        assert all(word in reply.upper() for word, _ in _PICTURES)

        largest = 0
        for label, recorded in (("one", one), ("four", four)):
            for sample in range(_SAMPLES):
                tokens, engine_ms, wall = _price(recorded.sent[0])
                largest = max(largest, tokens)
                print(  # noqa: T201
                    f"  {label} sample {sample}: {tokens} prompt tokens of {ctx},"
                    f" engine {engine_ms:.0f} ms, wall {wall:.2f} s, sm {_clock()}"
                )
        assert largest < ctx // 2, "four pictures leave less than half the window to the rest"
