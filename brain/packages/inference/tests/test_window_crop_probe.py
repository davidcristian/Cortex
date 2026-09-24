import json

from desktop_corpus import Desktop, Truth
from screen_paint import Rect, Screen
from window_crop_probe import VARIANTS, Picture, messages

from cortex_core import CaptureTarget

_FOCUS = next(variant for variant in VARIANTS if variant.target is CaptureTarget.FOCUS)
_WINDOW = Rect(8, 4, 40, 20)


def _desktop() -> Desktop:
    truth = Truth("clock", "the clock", "14:06", 15, inside=True)
    return Desktop("tiny", Screen(64, 36, (0, 0, 0)), _WINDOW, (truth,))


def _shot(width: int, height: int) -> Picture:
    return Picture(png=b"\x89PNG", width=width, height=height, region=_WINDOW)


async def _text(shot: Picture, *, sized: bool) -> str:
    return json.dumps(await messages(_desktop(), _FOCUS, shot, sized=sized))


async def test_a_sized_capture_says_the_window_was_downscaled() -> None:
    text = await _text(_shot(32, 16), sized=True)
    assert "32x16 image/png, downscaled from the window's 40x20, taken" in text


async def test_a_sized_capture_at_the_window_size_says_so() -> None:
    text = await _text(_shot(40, 20), sized=True)
    assert "40x20 image/png, at the window's own size, taken" in text


async def test_an_unsized_capture_says_nothing_about_the_window_size() -> None:
    text = await _text(_shot(32, 16), sized=False)
    assert "32x16 image/png, taken" in text
    assert "the window's" not in text


async def test_messages_send_the_window_size_by_default() -> None:
    text = json.dumps(await messages(_desktop(), _FOCUS, _shot(32, 16)))
    assert "downscaled from the window's 40x20" in text
