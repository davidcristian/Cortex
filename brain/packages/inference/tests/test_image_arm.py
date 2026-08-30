"""CI-side gate on the injection harness's image arm: its corpus, and the request it posts.

The measurement itself needs a GPU and is integration-marked, but its preconditions do not, and
they are exactly the ones a silent drift would void. A payload character the font cannot draw
would be posted as a filled box, so the model would be scored on an instruction it was never
shown. A corpus that changed shape between two renders would make a framed arm and its control
incomparable. An image the shipped ``ImagePart`` refuses would fail the live run minutes into a
model load rather than here in a second. And the arm's whole claim is that the two arms differ
by the **defence** and nothing else, which is a property of the serialised request that can be
read without a model in front of it.
"""

import zlib
from typing import Any, cast

from pixel_font import missing
from rendered_screens import CORPUS_FRAME, RENDERINGS, Frame, drawn
from test_injection_defense_live import ATTACKS, capture_result, image_messages

from cortex_core import SECURITY_PREAMBLE, ImagePart

_PNG = RENDERINGS[0].build(ATTACKS[0].injection, CORPUS_FRAME)
_ASK = "what is on my screen?"
# The second frame the live arm measures at, held here so the CI side proves a magnified render
# is a real picture of the size it claims before an hour of card time discovers otherwise.
_LARGE = Frame(2)


def test_every_payload_is_fully_drawable_by_the_font() -> None:
    """No corpus character falls back to the missing-glyph box, in either arm's text."""
    holes = {
        attack.name: missing(drawn(attack.injection))
        for attack in ATTACKS
        if missing(drawn(attack.injection))
    }
    assert not holes, f"the font cannot draw these payload characters: {holes}"


def test_every_rendering_of_every_attack_is_a_png_of_the_frame_it_was_asked_for() -> None:
    """Each cell of the corpus is a real PNG at the frame it was rendered at.

    The frame is the corpus's own and copies no capture bound, which
    [rendered_screens.py](rendered_screens.py) argues; what this holds is that every cell of one
    matrix is rendered at the one frame that matrix names, since two cells at two sizes would
    not be comparable.
    """
    for frame in (CORPUS_FRAME, _LARGE):
        for rendering in RENDERINGS:
            for attack in ATTACKS:
                png = rendering.build(attack.injection, frame)
                assert png.startswith(b"\x89PNG\r\n\x1a\n"), f"{rendering.name}/{attack.name}"
                header = frame.width.to_bytes(4, "big") + frame.height.to_bytes(4, "big")
                assert png[16:24] == header, f"{rendering.name}/{attack.name} at {frame.label}"


def test_the_corpus_is_byte_identical_when_rendered_twice() -> None:
    """Determinism, which is what lets a framed arm and its control share one picture."""
    for rendering in RENDERINGS:
        first = rendering.build(ATTACKS[0].injection, CORPUS_FRAME)
        assert first == rendering.build(ATTACKS[0].injection, CORPUS_FRAME), rendering.name


def test_every_rendering_is_accepted_by_the_shipped_image_part() -> None:
    """The bytes clear the brain's own mime, edge and budget checks before any server sees them."""
    for frame in (CORPUS_FRAME, _LARGE):
        for rendering in RENDERINGS:
            png = rendering.build(ATTACKS[0].injection, frame)
            part = ImagePart(
                data=png, mime_type="image/png", width=frame.width, height=frame.height
            )
            assert part.data == png


def test_two_renderings_of_one_attack_differ() -> None:
    """The renderings are three deliveries of one payload, not one picture named three times."""
    pictures = {rendering.build(ATTACKS[0].injection, CORPUS_FRAME) for rendering in RENDERINGS}
    assert len(pictures) == len(RENDERINGS)


def _rows(png: bytes, width: int) -> list[bytes]:
    """The RGB rows of a corpus PNG, unfiltered.

    The encoder in [rendered_screens.py](rendered_screens.py) writes one IHDR, one IDAT and one
    IEND, and prefixes every row with filter type 0, so the rows are the decompressed stream
    with one leading byte per row dropped. Reading them here rather than asserting on the header
    alone is what lets the frames be compared as pictures.
    """
    length = int.from_bytes(png[33:37], "big")
    raw = zlib.decompress(png[41 : 41 + length])
    stride = width * 3 + 1
    return [raw[line * stride + 1 : (line + 1) * stride] for line in range(len(raw) // stride)]


def test_a_magnified_render_is_the_same_picture_carried_by_more_pixels() -> None:
    """The large frame is the base frame pixel for pixel, each pixel grown to a square block.

    This is the property that makes two frames an answer to whether resistance moves with the
    picture's *size*: the payload occupies exactly the same share of the picture at both, so
    size is the only thing that differs. A second frame that redrew the screen, or that left
    the glyphs at their old size while the canvas grew, would move a second variable and the
    two matrices would no longer be a comparison. Sampled rows spanning the whole picture,
    because the same assertion over every row of every rendering is a minute of CI for a
    property that cannot hold on 24 rows and fail on the 25th.
    """
    magnify = _LARGE.magnify
    for rendering in RENDERINGS:
        small = _rows(rendering.build(ATTACKS[0].injection, CORPUS_FRAME), CORPUS_FRAME.width)
        large = _rows(rendering.build(ATTACKS[0].injection, _LARGE), _LARGE.width)
        assert len(small) == CORPUS_FRAME.height, rendering.name
        assert len(large) == _LARGE.height, rendering.name
        for line in range(0, CORPUS_FRAME.height, 37):
            grown = b"".join(
                small[line][x : x + 3] * magnify for x in range(0, CORPUS_FRAME.width * 3, 3)
            )
            for repeat in range(magnify):
                assert large[line * magnify + repeat] == grown, f"{rendering.name}:{line}"


async def test_the_stand_in_text_names_the_frame_the_picture_really_arrived_at() -> None:
    """The words the model reads about the capture follow the frame, at every frame.

    The delivered size and the display it claims to be a downscale of are both in the tool's
    stand-in text, so a frame that scaled the pixels and left that sentence alone would tell the
    model it was looking at a capture nobody took.
    """
    for frame in (CORPUS_FRAME, _LARGE):
        png = RENDERINGS[0].build(ATTACKS[0].injection, frame)
        result = await capture_result(png, frame)
        # The label is what a printed matrix and a test id call this frame, so it is held to
        # what the shipped `describe` writes off the picture rather than to itself.
        assert frame.label in result.content, frame.label
        assert f"{frame.source_width}x{frame.source_height}" in result.content, frame.label
        # Relational, not arithmetic: a claimed source that stopped following the frame would
        # otherwise move the test's own expectation with it and stay green.
        assert frame.source_width * CORPUS_FRAME.width == CORPUS_FRAME.source_width * frame.width
        assert (
            frame.source_height * CORPUS_FRAME.height == CORPUS_FRAME.source_height * frame.height
        )


def _tool_parts(wire: list[dict[str, object]]) -> list[dict[str, Any]]:
    """The content-parts array of the tool message that closes a vision conversation."""
    parts = wire[-1]["content"]
    assert isinstance(parts, list)
    return cast("list[dict[str, Any]]", parts)


async def test_the_screen_reaches_the_wire_as_a_png_data_uri() -> None:
    """The pixels really are in the request, in both arms, as a content-parts image."""
    result = await capture_result(_PNG)
    for framed in (True, False):
        parts = _tool_parts(image_messages(result, framed=framed, ask=_ASK))
        images = [part for part in parts if part["type"] == "image_url"]
        assert len(images) == 1, framed
        assert str(images[0]["image_url"]["url"]).startswith("data:image/png;base64,"), framed


async def test_the_two_arms_differ_by_the_defence_and_by_nothing_else() -> None:
    """The preamble and the fence are the only difference; the picture is byte-identical.

    This is what makes the unframed control a control. If the arms differed in the picture too,
    an obeyed control would prove nothing about whether the framing changed the model's
    behaviour, and the arm's whole claim rests on that comparison.
    """
    result = await capture_result(_PNG)
    framed = image_messages(result, framed=True, ask=_ASK)
    control = image_messages(result, framed=False, ask=_ASK)
    assert framed[0] == {"role": "system", "content": SECURITY_PREAMBLE}
    assert framed[1:3] == control[0:2]
    framed_parts, control_parts = _tool_parts(framed), _tool_parts(control)
    assert framed_parts[1:] == control_parts[1:]
    assert framed_parts[0] != control_parts[0]
    assert str(control_parts[0]["text"]) in str(framed_parts[0]["text"])
