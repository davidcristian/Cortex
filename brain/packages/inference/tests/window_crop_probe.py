"""The two conditions of the window-crop legibility measurement, and how a transcription is scored.

``display`` sends the whole frame downscaled to the capture edge, which is what the deployment
sends today; ``focus`` sends the focused window's rectangle through the same downscale.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from desktop_corpus import Desktop, Truth
from screen_paint import Rect, cap_height, downscale, encode_png
from test_injection_defense_live import folded

from cortex_core import (
    CAPTURE_SCREEN_TOOL_NAME,
    CaptureScreenTool,
    CaptureTarget,
    ImagePart,
    InMemoryBodyGateway,
    Message,
    Role,
    ScreenCapture,
    ToolCall,
    call_message,
    new_nonce,
    result_message,
    security_preamble_message,
)
from cortex_inference.request import to_openai_message

_CAPTURED_AT = datetime(2026, 8, 10, 9, 14, tzinfo=UTC)
_TURN = "window-crop-probe"
_CALL_ID = "c1"

# The word the question offers instead of a guess. It is scored as a decline rather than a miss,
# which is the difference the recorded measurement had to make when the model invented 38 strings.
DECLINE = "UNREADABLE"

_INSTRUCTION = (
    "Read the attached picture of a screen and transcribe the exact text at each place listed "
    "below. Answer with a JSON object whose keys are the ids given here. Each value is the "
    f"text as it appears on the screen, character for character. If you cannot read it, or it "
    f"is not in the picture, answer exactly {DECLINE}. Do not guess and do not describe: a "
    f"wrong transcription is worse than {DECLINE}."
)


@dataclass(frozen=True)
class Variant:
    """One way of pointing a capture at a desktop."""

    name: str
    target: CaptureTarget

    def region(self, desktop: Desktop) -> Rect:
        """Return the rectangle this variant reads out of the frame."""
        if self.target is CaptureTarget.FOCUS:
            return desktop.window
        return Rect(0, 0, desktop.screen.width, desktop.screen.height)


VARIANTS: tuple[Variant, ...] = (
    Variant("display", CaptureTarget.DISPLAY),
    Variant("focus", CaptureTarget.FOCUS),
)


@dataclass(frozen=True)
class Picture:
    """The encoded capture one variant produces, and the geometry that explains it."""

    png: bytes
    width: int
    height: int
    region: Rect

    @property
    def resampled(self) -> bool:
        """Whether the body's box filter ran, or the identity path passed it through untouched."""
        return (self.width, self.height) != (self.region.width, self.region.height)


def picture(desktop: Desktop, variant: Variant, bound: int) -> Picture:
    """Put the desktop through the body's own crop and downscale for this variant."""
    region = variant.region(desktop)
    width, height, rgb = downscale(desktop.screen, region, bound)
    return Picture(encode_png(width, height, rgb), width, height, region)


async def messages(desktop: Desktop, variant: Variant, shot: Picture) -> list[dict[str, object]]:
    """Build the whole vision conversation, serialised by the backend's own message mapper."""
    capture = ScreenCapture(
        image=ImagePart(data=shot.png, mime_type="image/png", width=shot.width, height=shot.height),
        source_width=desktop.screen.width,
        source_height=desktop.screen.height,
        captured_at=_CAPTURED_AT,
        target=variant.target,
    )
    arguments = {"target": variant.target.value}
    tool = CaptureScreenTool(InMemoryBodyGateway(capture=capture))
    call = ToolCall(id=_CALL_ID, name=CAPTURE_SCREEN_TOOL_NAME, arguments=arguments)
    result = await tool.invoke(call)
    conversation: list[Message] = [
        security_preamble_message(_CAPTURED_AT, _TURN),
        Message(role=Role.USER, text=ask(desktop.truths), at=_CAPTURED_AT, turn_id=_TURN),
        call_message("", (call,), _CAPTURED_AT, _TURN),
        result_message(result, _CAPTURED_AT, _TURN, nonce=new_nonce()),
    ]
    return [to_openai_message(message) for message in conversation]


def ask(truths: tuple[Truth, ...]) -> str:
    """Build the ask, which names every string by its place on screen and never by its value."""
    places = "\n".join(f"- {truth.key}: {truth.where}" for truth in truths)
    return f"{_INSTRUCTION}\n\n{places}"


def schema(truths: tuple[Truth, ...]) -> dict[str, object]:
    """Build a JSON schema with one required string property per ground truth, so that scoring is
    mechanical.
    """
    properties = {truth.key: {"type": "string"} for truth in truths}
    return {
        "type": "object",
        "properties": properties,
        "required": [truth.key for truth in truths],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class Reading:
    """What one variant made of one ground-truth string."""

    truth: Truth
    answer: str
    grade: str

    @property
    def read(self) -> bool:
        """Whether the ground truth came back."""
        return self.grade == "read"


def readings(truths: tuple[Truth, ...], answers: dict[str, Any]) -> tuple[Reading, ...]:
    """Score one variant's reply: read, declined, or wrong, in that order of precedence."""
    scored: list[Reading] = []
    for truth in truths:
        raw = answers.get(truth.key, "")
        answer = raw if isinstance(raw, str) else str(raw)
        scored.append(Reading(truth=truth, answer=answer, grade=_grade(truth, answer)))
    return tuple(scored)


def _grade(truth: Truth, answer: str) -> str:
    """A hit is the ground truth appearing in the answer, with confusable glyphs folded."""
    if folded(truth.value) in folded(answer):
        return "read"
    if DECLINE in answer.upper() or not answer.strip():
        return "declined"
    return "wrong"


def tally(scored: Sequence[Reading]) -> tuple[int, int, int]:
    """Count how many of a set of readings were read, wrong, and declined."""
    read = sum(1 for reading in scored if reading.grade == "read")
    wrong = sum(1 for reading in scored if reading.grade == "wrong")
    return (read, wrong, len(scored) - read - wrong)


def report(results: Mapping[str, Sequence[Reading]]) -> str:
    """Render the whole table: totals per variant, then hits per physical type size."""
    lines = ["", "  arm       scope    read  wrong  declined  of"]
    for variant, scored in results.items():
        for scope, subset in (("inside", _inside(scored)), ("outside", _outside(scored))):
            read, wrong, declined = tally(subset)
            lines.append(
                f"  {variant:9s} {scope:8s} {read:4d} {wrong:6d} {declined:9d} {len(subset):3d}"
            )
    variants = list(results)
    lines += ["", "  strings inside the focused window, read per physical type size", ""]
    lines.append("  size  cap  " + "  ".join(f"{variant:>9s}" for variant in variants))
    for size in sorted({reading.truth.size for reading in _inside(next(iter(results.values())))}):
        cells: list[str] = []
        for variant in variants:
            rows = [row for row in _inside(results[variant]) if row.truth.size == size]
            cells.append(f"{sum(1 for row in rows if row.read):5d}/{len(rows):<3d}")
        lines.append(f"  {size:4d}  {cap_height(size):3d}  " + "  ".join(cells))
    return "\n".join(lines + _differences(results))


def _differences(results: Mapping[str, Sequence[Reading]]) -> list[str]:
    """Render every string the two variants disagreed about, with what each of them said."""
    variants = list(results)
    by_key = {variant: {row.truth.key: row for row in results[variant]} for variant in variants}
    lines = ["", "  where the arms disagreed, and what each said", ""]
    for key, first in by_key[variants[0]].items():
        grades = [by_key[variant][key].grade for variant in variants]
        if len(set(grades)) == 1:
            continue
        lines.append(f"  {key} ({first.truth.size} px, {'in' if first.truth.inside else 'out'})")
        lines.append(f"      truth  {first.truth.value!r}")
        for variant in variants:
            row = by_key[variant][key]
            lines.append(f"      {variant:8s} {row.grade:9s} {row.answer!r}")
    return lines


def _inside(scored: Sequence[Reading]) -> list[Reading]:
    """Return the readings whose ground truth lies inside the focused window."""
    return [reading for reading in scored if reading.truth.inside]


def _outside(scored: Sequence[Reading]) -> list[Reading]:
    """Return the readings whose ground truth lies outside it, which a crop cannot include."""
    return [reading for reading in scored if not reading.truth.inside]
