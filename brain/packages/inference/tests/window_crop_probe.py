"""The two arms of the window-crop legibility measurement, and how a transcription is scored.

One desktop is delivered to the model twice (ADR-0029):

- **display**, the whole 3840x2160 frame box-filtered down to the capture edge, which is what
  the shipped deployment sends today and the control this measurement is read against;
- **focus**, the sub-rectangle a focused-window capture would produce, put through the same
  ``downscale``, which for a window already inside the capture edge takes the identity arm and
  crosses pixel for pixel.

Everything either arm sends is built by shipped code: ``CaptureScreenTool`` over an in-memory
body, ``describe``'s stand-in text, ``result_message``'s fence, ``security_preamble_message``,
and the inference adapter's own wire mapper. The two requests differ in the picture and in the
one sentence the shipped tool writes about it, which is exactly what differs in production; the
ask itself is byte-identical, so no arm is asked an easier question.

Scoring counts three outcomes rather than two, because the model's failure mode here is not
silence. Asked with "unreadable" offered as an answer, the cortex has confidently invented
strings it could not read, so a transcription is **read**, **wrong**, or **declined**, and a
number that pooled the last two would flatter both arms.
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

# The word the ask offers instead of a guess. Scored as a decline rather than as a miss, which
# is the distinction the recorded measurement had to make when the model invented 38 strings.
DECLINE = "UNREADABLE"

_INSTRUCTION = (
    "Read the attached picture of a screen and transcribe the exact text at each place listed "
    "below. Answer with a JSON object whose keys are the ids given here. Each value is the "
    f"text as it appears on the screen, character for character. If you cannot read it, or it "
    f"is not in the picture, answer exactly {DECLINE}. Do not guess and do not describe: a "
    f"wrong transcription is worse than {DECLINE}."
)


@dataclass(frozen=True)
class Arm:
    """One way of pointing a capture at a desktop."""

    name: str
    target: CaptureTarget

    def region(self, desktop: Desktop) -> Rect:
        """The rectangle this arm reads out of the frame."""
        if self.target is CaptureTarget.FOCUS:
            return desktop.window
        return Rect(0, 0, desktop.screen.width, desktop.screen.height)


ARMS: tuple[Arm, ...] = (Arm("display", CaptureTarget.DISPLAY), Arm("focus", CaptureTarget.FOCUS))


@dataclass(frozen=True)
class Picture:
    """The encoded capture one arm produces, and the geometry that explains it."""

    png: bytes
    width: int
    height: int
    region: Rect

    @property
    def resampled(self) -> bool:
        """Whether the body's box filter ran, or the identity arm carried it untouched."""
        return (self.width, self.height) != (self.region.width, self.region.height)


def picture(desktop: Desktop, arm: Arm, bound: int) -> Picture:
    """Put the desktop through the body's own crop and downscale for this arm."""
    region = arm.region(desktop)
    width, height, rgb = downscale(desktop.screen, region, bound)
    return Picture(encode_png(width, height, rgb), width, height, region)


async def messages(desktop: Desktop, arm: Arm, shot: Picture) -> list[dict[str, object]]:
    """The whole vision conversation, serialised by the backend's own message mapper."""
    capture = ScreenCapture(
        image=ImagePart(data=shot.png, mime_type="image/png", width=shot.width, height=shot.height),
        source_width=desktop.screen.width,
        source_height=desktop.screen.height,
        captured_at=_CAPTURED_AT,
        target=arm.target,
    )
    arguments = {"target": arm.target.value}
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
    """The ask, which names every string by its place on the screen and never by its value."""
    places = "\n".join(f"- {truth.key}: {truth.where}" for truth in truths)
    return f"{_INSTRUCTION}\n\n{places}"


def schema(truths: tuple[Truth, ...]) -> dict[str, object]:
    """A JSON schema with one required string property per ground truth, so scoring is
    mechanical."""
    properties = {truth.key: {"type": "string"} for truth in truths}
    return {
        "type": "object",
        "properties": properties,
        "required": [truth.key for truth in truths],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class Reading:
    """What one arm made of one ground-truth string."""

    truth: Truth
    answer: str
    verdict: str

    @property
    def read(self) -> bool:
        """Whether the ground truth came back."""
        return self.verdict == "read"


def readings(truths: tuple[Truth, ...], answers: dict[str, Any]) -> tuple[Reading, ...]:
    """Score one arm's reply: read, declined, or wrong, in that order of precedence."""
    scored: list[Reading] = []
    for truth in truths:
        raw = answers.get(truth.key, "")
        answer = raw if isinstance(raw, str) else str(raw)
        scored.append(Reading(truth=truth, answer=answer, verdict=_verdict(truth, answer)))
    return tuple(scored)


def _verdict(truth: Truth, answer: str) -> str:
    """A hit is the ground truth appearing in the answer, with confusable glyphs folded."""
    if folded(truth.value) in folded(answer):
        return "read"
    if DECLINE in answer.upper() or not answer.strip():
        return "declined"
    return "wrong"


def tally(scored: Sequence[Reading]) -> tuple[int, int, int]:
    """How many of a set of readings were read, wrong, and declined."""
    read = sum(1 for reading in scored if reading.verdict == "read")
    wrong = sum(1 for reading in scored if reading.verdict == "wrong")
    return (read, wrong, len(scored) - read - wrong)


def report(results: Mapping[str, Sequence[Reading]]) -> str:
    """The whole printed table: totals per arm, then hits per physical type size.

    Split by whether the focused window contains the string, because the two halves answer
    different questions. Inside the window, both arms carry the same pixels and the comparison
    is legibility alone. Outside it, the crop cannot see the string at all, which is the cost
    of pointing a capture at one window and is reported rather than hidden.
    """
    lines = ["", "  arm       scope    read  wrong  declined  of"]
    for arm, scored in results.items():
        for scope, subset in (("inside", _inside(scored)), ("outside", _outside(scored))):
            read, wrong, declined = tally(subset)
            lines.append(
                f"  {arm:9s} {scope:8s} {read:4d} {wrong:6d} {declined:9d} {len(subset):3d}"
            )
    arms = list(results)
    lines += ["", "  strings inside the focused window, read per physical type size", ""]
    lines.append("  size  cap  " + "  ".join(f"{arm:>9s}" for arm in arms))
    for size in sorted({reading.truth.size for reading in _inside(next(iter(results.values())))}):
        cells: list[str] = []
        for arm in arms:
            rows = [row for row in _inside(results[arm]) if row.truth.size == size]
            cells.append(f"{sum(1 for row in rows if row.read):5d}/{len(rows):<3d}")
        lines.append(f"  {size:4d}  {cap_height(size):3d}  " + "  ".join(cells))
    return "\n".join(lines + _differences(results))


def _differences(results: Mapping[str, Sequence[Reading]]) -> list[str]:
    """Every string the arms disagreed about, with what each of them said.

    Printed rather than summarised because a count is not readable evidence: a hit is a
    substring match over folded glyphs, so a short ground truth can in principle be matched by
    a longer wrong answer, and the only way to know a table is telling the truth is to read the
    transcriptions that moved it.
    """
    arms = list(results)
    by_key = {arm: {row.truth.key: row for row in results[arm]} for arm in arms}
    lines = ["", "  where the arms disagreed, and what each said", ""]
    for key, first in by_key[arms[0]].items():
        verdicts = [by_key[arm][key].verdict for arm in arms]
        if len(set(verdicts)) == 1:
            continue
        lines.append(f"  {key} ({first.truth.size} px, {'in' if first.truth.inside else 'out'})")
        lines.append(f"      truth  {first.truth.value!r}")
        for arm in arms:
            row = by_key[arm][key]
            lines.append(f"      {arm:8s} {row.verdict:9s} {row.answer!r}")
    return lines


def _inside(scored: Sequence[Reading]) -> list[Reading]:
    """The readings whose ground truth lies inside the focused window."""
    return [reading for reading in scored if reading.truth.inside]


def _outside(scored: Sequence[Reading]) -> list[Reading]:
    """The readings whose ground truth lies outside it, which a crop cannot carry."""
    return [reading for reading in scored if not reading.truth.inside]
