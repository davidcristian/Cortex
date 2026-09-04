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
from rendered_screens import (
    CORPUS_FRAME,
    CORPUS_PAYLOAD_SCALE,
    CORPUS_TYPE_SCALE,
    RENDERINGS,
    Frame,
    Rendering,
    TypeScale,
    drawn,
)
from test_injection_defense_live import (
    ATTACKS,
    ENGINE_BUDGET,
    MODELS,
    SHIPPED_BUDGET,
    TYPE_SCALES,
    VISION_MODELS,
    capture_result,
    image_messages,
    server_argv,
)

from cortex_core import SECURITY_PREAMBLE, ImagePart

_PNG = RENDERINGS[0].build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE)
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
                png = rendering.build(attack.injection, frame, CORPUS_TYPE_SCALE)
                assert png.startswith(b"\x89PNG\r\n\x1a\n"), f"{rendering.name}/{attack.name}"
                header = frame.width.to_bytes(4, "big") + frame.height.to_bytes(4, "big")
                assert png[16:24] == header, f"{rendering.name}/{attack.name} at {frame.label}"


def test_the_corpus_is_byte_identical_when_rendered_twice() -> None:
    """Rendering a cell twice gives the same bytes, so an arm and its control share a picture."""
    for rendering in RENDERINGS:
        first = rendering.build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE)
        assert first == rendering.build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE), (
            rendering.name
        )


def test_every_rendering_is_accepted_by_the_shipped_image_part() -> None:
    """The bytes clear the brain's own mime, edge and budget checks before any server sees them."""
    for frame in (CORPUS_FRAME, _LARGE):
        for rendering in RENDERINGS:
            png = rendering.build(ATTACKS[0].injection, frame, CORPUS_TYPE_SCALE)
            part = ImagePart(
                data=png, mime_type="image/png", width=frame.width, height=frame.height
            )
            assert part.data == png


def test_two_renderings_of_one_attack_differ() -> None:
    """The renderings are three deliveries of one payload, not one picture named three times."""
    pictures = {
        rendering.build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE)
        for rendering in RENDERINGS
    }
    assert len(pictures) == len(RENDERINGS)


def _rows(png: bytes, width: int) -> list[bytes]:
    """Return the RGB rows of a corpus PNG, unfiltered.

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
    two matrices would no longer be a comparison. Rows are sampled across the whole picture,
    because the same assertion over every row of every rendering costs a minute of CI for a
    property that cannot hold on 24 rows and fail on the 25th.
    """
    magnify = _LARGE.magnify
    for rendering in RENDERINGS:
        small = _rows(
            rendering.build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE),
            CORPUS_FRAME.width,
        )
        large = _rows(
            rendering.build(ATTACKS[0].injection, _LARGE, CORPUS_TYPE_SCALE), _LARGE.width
        )
        assert len(small) == CORPUS_FRAME.height, rendering.name
        assert len(large) == _LARGE.height, rendering.name
        for line in range(0, CORPUS_FRAME.height, 37):
            grown = b"".join(
                small[line][x : x + 3] * magnify for x in range(0, CORPUS_FRAME.width * 3, 3)
            )
            for repeat in range(magnify):
                assert large[line * magnify + repeat] == grown, f"{rendering.name}:{line}"


def test_every_payload_size_the_sweep_runs_at_is_a_png_of_its_frame() -> None:
    """A smaller payload is still a whole screen, at both frames."""
    for type_scale in TYPE_SCALES:
        for frame in (CORPUS_FRAME, _LARGE):
            for rendering in RENDERINGS:
                png = rendering.build(ATTACKS[0].injection, frame, type_scale)
                header = frame.width.to_bytes(4, "big") + frame.height.to_bytes(4, "big")
                assert png[16:24] == header, f"{rendering.name} at {type_scale.label}"


def test_a_payload_size_moves_nothing_above_the_payload() -> None:
    """The first row a payload size changes is the row the rendering declares, in every rendering.

    This is what makes the sweep a sweep of one variable, and it is asserted as the exact line
    rather than as "nothing above it": a declared top that drifted upward would leave a weaker
    claim passing, since every row above the real payload is identical either way. Below the
    payload the mail client's sign-off does follow the paragraph, as a shorter message would on a
    real screen, so the claim stops at that line rather than covering the whole picture.
    """
    for rendering in RENDERINGS:
        corpus = _rows(
            rendering.build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE),
            CORPUS_FRAME.width,
        )
        for type_scale in TYPE_SCALES[1:]:
            smaller = _rows(
                rendering.build(ATTACKS[0].injection, CORPUS_FRAME, type_scale), CORPUS_FRAME.width
            )
            moved = [line for line, row in enumerate(smaller) if row != corpus[line]]
            assert min(moved) == rendering.payload_top, (
                f"{rendering.name} at {type_scale.label}: the first row this size changes is "
                f"{min(moved)} and the rendering declares {rendering.payload_top}"
            )


def _painted(rendering: Rendering, type_scale: TypeScale) -> list[tuple[int, int]]:
    """The pixels of a screen the injected instruction paints at this size, as row and column.

    Read as the difference against the same screen drawn with no instruction in it, so the
    payload's share of the picture is measured rather than inferred from the glyph scale.
    """
    blank = _rows(rendering.build("", CORPUS_FRAME, type_scale), CORPUS_FRAME.width)
    drawn_screen = _rows(
        rendering.build(ATTACKS[0].injection, CORPUS_FRAME, type_scale), CORPUS_FRAME.width
    )
    return [
        (line, x // 3)
        for line, (row, other) in enumerate(zip(blank, drawn_screen, strict=True))
        for x in range(0, len(row), 3)
        if row[x : x + 3] != other[x : x + 3]
    ]


def test_a_smaller_payload_is_set_in_the_same_column_of_pixels() -> None:
    """A wrapped line is the same width in pixels at every size, whatever width it is given.

    The paragraph keeps the column it is set in, so a smaller payload reads as body text rather
    than as a short block of small type. Asserted as the relation between the two, since a
    columns rule that stopped following the glyph scale could otherwise be read back out of the
    expectation it computed.
    """
    for corpus_columns in (12, 24, 42, 48, 68):
        for type_scale in TYPE_SCALES:
            assert (
                type_scale.columns(corpus_columns) * type_scale.scale
                == corpus_columns * CORPUS_PAYLOAD_SCALE
            ), f"{corpus_columns} at {type_scale.label}"


def test_the_pitch_between_a_payloads_lines_follows_its_glyphs() -> None:
    """The lines close up as the glyphs shrink, so a small payload is a paragraph of small type.

    Held as a proportion within the one pixel an integer division can lose, rather than as an
    expectation computed from the rule under test.
    """
    for corpus_leading in (18, 40, 42, 46):
        for type_scale in TYPE_SCALES:
            drift = abs(
                type_scale.leading(corpus_leading) * CORPUS_PAYLOAD_SCALE
                - corpus_leading * type_scale.scale
            )
            assert drift < CORPUS_PAYLOAD_SCALE, f"{corpus_leading} at {type_scale.label}"


def test_a_smaller_payload_size_paints_a_smaller_share_of_the_screen() -> None:
    """The share falls with every step of the sweep, and never to nothing.

    The sweep's variable is what fraction of the screen the instruction occupies, so a size that
    painted the same share as the one above it would be a second row measuring the first, and one
    that painted nothing would be a row with no attack in it.
    """
    for rendering in RENDERINGS:
        painted = [len(_painted(rendering, type_scale)) for type_scale in TYPE_SCALES]
        assert all(count > 0 for count in painted), f"{rendering.name}: {painted}"
        assert painted == sorted(painted, reverse=True), f"{rendering.name}: {painted}"
        assert len(set(painted)) == len(painted), f"{rendering.name}: {painted}"


async def test_the_stand_in_text_names_the_frame_the_picture_really_arrived_at() -> None:
    """The words the model reads about the capture follow the frame, at every frame.

    The delivered size and the display it claims to be a downscale of are both in the tool's
    stand-in text, so a frame that scaled the pixels and left that sentence alone would tell the
    model it was looking at a capture nobody took.
    """
    for frame in (CORPUS_FRAME, _LARGE):
        png = RENDERINGS[0].build(ATTACKS[0].injection, frame, CORPUS_TYPE_SCALE)
        result = await capture_result(png, frame)
        # The label is what a printed matrix and a test id call this frame, so it is held to
        # what the shipped `describe` writes off the picture rather than to itself.
        assert frame.label in result.content, frame.label
        assert f"{frame.source_width}x{frame.source_height}" in result.content, frame.label
        # The comparison is relational rather than arithmetic, because a claimed source that
        # stopped following the frame would otherwise move this expectation along with it.
        assert frame.source_width * CORPUS_FRAME.width == CORPUS_FRAME.source_width * frame.width
        assert (
            frame.source_height * CORPUS_FRAME.height == CORPUS_FRAME.source_height * frame.height
        )


def test_the_arm_starts_its_server_with_the_deployments_own_image_budget() -> None:
    """A seeing row's command line carries the budget pair, and it carries it as a pair.

    The budget decides how many tokens one picture may occupy, so a row measured without the
    deployment's own budget is a row about a stack nobody runs. The two flags travel together
    because raising the first without the second aborts llama-server on the first oversized
    picture, which is a failure an hour into a live run rather than here.
    """
    for model in VISION_MODELS:
        argv = server_argv(model, SHIPPED_BUDGET)
        assert argv[-4:] == (
            "--image-max-tokens",
            str(SHIPPED_BUDGET.image_max_tokens),
            "--ubatch-size",
            str(SHIPPED_BUDGET.image_max_tokens),
        ), model.label
        assert "--mmproj" in argv, model.label


def test_the_engine_budget_row_starts_with_neither_flag() -> None:
    """The row that reproduces every pixel measurement published before the budget moved.

    Naming the engine's own defaults back at it would be a different command line from the one
    those rows ran, so this budget emits nothing at all.
    """
    for model in VISION_MODELS:
        argv = server_argv(model, ENGINE_BUDGET)
        assert "--image-max-tokens" not in argv, model.label
        assert "--ubatch-size" not in argv, model.label


def test_a_text_only_row_is_started_without_the_image_budget_pair() -> None:
    """The pair hangs off the projector, exactly as the shipped model host hangs it off the tier.

    A text arm row cannot be handed a picture, so a micro-batch raised for one would spend VRAM
    on nothing and would make the text arm's command line differ from the one its published rows
    ran with.
    """
    for model in MODELS:
        if model.mmproj is None:
            assert server_argv(model, SHIPPED_BUDGET) == server_argv(model, ENGINE_BUDGET)
            assert "--ubatch-size" not in server_argv(model, SHIPPED_BUDGET), model.label


def _tool_parts(wire: list[dict[str, object]]) -> list[dict[str, Any]]:
    """Return the content-parts array of the tool message closing a vision conversation."""
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
